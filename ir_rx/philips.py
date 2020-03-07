# philips.py Decoder for IR remote control using synchronous code
# Supports Philips RC-5 RC-6 mode 0 protocols.

# Author: Peter Hinch
# Copyright Peter Hinch 2020 Released under the MIT license

from utime import ticks_us, ticks_diff
from ir_rx import IR_RX

class RC5_IR(IR_RX):
    def __init__(self, pin, callback, *args):
        # Block lasts <= 30ms and has <= 28 edges
        super().__init__(pin, 28, 30, callback, *args)

    def decode(self, _):
        try:
            nedges = self.edge  # No. of edges detected
            if not 14 <= nedges <= 28:
                raise RuntimeError(self.OVERRUN if nedges > 28 else self.BADSTART)
            # Regenerate bitstream
            bits = 0
            bit = 1
            for x in range(1, nedges):
                width = ticks_diff(self._times[x], self._times[x - 1])
                if not 500 < width < 2000:
                    raise RuntimeError(self.BADBLOCK)
                for _ in range(1 if width < 1334 else 2):
                    bits <<= 1
                    bits |= bit
                bit ^= 1
            self.verbose and print(bin(bits))  # Matches inverted scope waveform
            # Decode Manchester code
            x = 30
            while not bits >> x:
                x -= 1
            m0 = 1 << x  # Mask MS two bits (always 01)
            m1 = m0 << 1
            v = 0  # 14 bit bitstream
            for _ in range(14):
                v <<= 1
                b0 = (bits & m0) > 0
                b1 = (bits & m1) > 0
                if b0 == b1:
                    raise RuntimeError(self.BADBLOCK)
                v |= b0
                m0 >>= 2
                m1 >>= 2
            # Split into fields (val, addr, ctrl)
            val = (v & 0x3f) | (0x40 if ((v >> 12) & 1) else 0)
            addr = (v >> 6) & 0x1f
            ctrl = (v >> 11) & 1

        except RuntimeError as e:
            val, addr, ctrl = e.args[0], 0, 0
        # Set up for new data burst and run user callback
        self.do_callback(val, addr, ctrl)

class RC6_M0(IR_RX):
    # Even on Pyboard D the 444μs nominal pulses can be recorded as up to 705μs
    # Scope shows 360-520 μs (-84μs +76μs relative to nominal)
    # Header nominal 2666, 889, 444, 889, 444, 444, 444, 444 carrier ON at end
    hdr = ((1800, 4000), (593, 1333), (222, 750), (593, 1333), (222, 750), (222, 750), (222, 750), (222, 750))
    def __init__(self, pin, callback, *args):
        # Block lasts 23ms nominal and has <=44 edges
        super().__init__(pin, 44, 30, callback, *args)

    def decode(self, _):
        try:
            nedges = self.edge  # No. of edges detected
            if not 22 <= nedges <= 44:
                raise RuntimeError(self.OVERRUN if nedges > 28 else self.BADSTART)
            for x, lims in enumerate(self.hdr):
                width = ticks_diff(self._times[x + 1], self._times[x])
                if not (lims[0] < width < lims[1]):
                    self.verbose and print('Bad start', x, width, lims)
                    raise RuntimeError(self.BADSTART)
            x += 1
            width = ticks_diff(self._times[x + 1], self._times[x])
            # 2nd bit of last 0 is 444μs (0) or 1333μs (1)
            if not 222 < width < 1555:
                self.verbose and print('Bad block 1 Width', width, 'x', x)
                raise RuntimeError(self.BADBLOCK)
            short = width < 889
            v = int(not short)
            bit = v
            bits = 1  # Bits decoded
            x += 1 + int(short)
            width = ticks_diff(self._times[x + 1], self._times[x])
            if not 222 < width < 1555:
                self.verbose and print('Bad block 2 Width', width, 'x', x)
                raise RuntimeError(self.BADBLOCK)
            short = width < 1111
            if not short:
                bit ^= 1
            x += 1 + int(short)  # If it's short, we know width of next
            v <<= 1
            v |= bit  # MSB of result
            bits += 1
            # Decode bitstream
            while bits < 17:
                # -1 convert count to index, -1 because we look ahead
                if x > nedges - 2:
                    raise RuntimeError(self.BADBLOCK)
                # width is 444/889 nominal
                width = ticks_diff(self._times[x + 1], self._times[x])
                if not 222 < width < 1111:
                    self.verbose and print('Bad block 3 Width', width, 'x', x)
                    raise RuntimeError(self.BADBLOCK)
                short = width < 666
                if not short:
                    bit ^= 1
                v <<= 1
                v |= bit
                bits += 1
                x += 1 + int(short)

            if self.verbose:
                 ss = '20-bit format {:020b} x={} nedges={} bits={}'
                 print(ss.format(v, x, nedges, bits))

            val = v & 0xff
            addr = (v >> 8) & 0xff
            ctrl = (v >> 16) & 1
        except RuntimeError as e:
            val, addr, ctrl = e.args[0], 0, 0
        # Set up for new data burst and run user callback
        self.do_callback(val, addr, ctrl)
