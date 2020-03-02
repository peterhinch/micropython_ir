# ir_rx.py Decoder for IR remote control using synchronous code
# Supports RC-5 RC-6 mode 0 and NEC protocols.
# For a remote using NEC see https://www.adafruit.com/products/389

# Author: Peter Hinch
# Copyright Peter Hinch 2020 Released under the MIT license

from sys import platform
from micropython import const
from machine import Timer
from array import array
from utime import ticks_us, ticks_diff

if platform == 'pyboard':
    from pyb import Pin, ExtInt
else:
    from machine import Pin

ESP32 = platform == 'esp32' or platform == 'esp32_LoBo'

# Save RAM
# from micropython import alloc_emergency_exception_buf
# alloc_emergency_exception_buf(100)

# Result codes (accessible to application)
# Repeat button code
REPEAT = -1
# Error codes
BADSTART = -2
BADBLOCK = -3
BADREP = -4
OVERRUN = -5
BADDATA = -6
BADADDR = -7


# On 1st edge start a block timer. While the timer is running, record the time
# of each edge. When the timer times out decode the data. Duration must exceed
# the worst case block transmission time, but be less than the interval between
# a block start and a repeat code start (~108ms depending on protocol)

class IR_RX():
    verbose = False
    def __init__(self, pin, nedges, tblock, callback, *args):  # Optional args for callback
        self._nedges = nedges
        self._tblock = tblock
        self.callback = callback
        self.args = args

        self._times = array('i',  (0 for _ in range(nedges + 1)))  # +1 for overrun
        if platform == 'pyboard':
            ei = ExtInt(pin, ExtInt.IRQ_RISING_FALLING, Pin.PULL_NONE, self._cb_pin)
        elif ESP32:
            ei = pin.irq(handler = self._cb_pin, trigger = (Pin.IRQ_FALLING | Pin.IRQ_RISING))
        else:
            ei = pin.irq(handler = self._cb_pin, trigger = (Pin.IRQ_FALLING | Pin.IRQ_RISING), hard = True)
        self._eint = ei  # Keep reference??
        self.edge = 0
        self.tim = Timer(-1)  # Sofware timer
        self.cb = self.decode


    # Pin interrupt. Save time of each edge for later decode.
    def _cb_pin(self, line):
        t = ticks_us()
        # On overrun ignore pulses until software timer times out
        if self.edge <= self._nedges:  # Allow 1 extra pulse to record overrun
            if not self.edge:  # First edge received
                self.tim.init(period=self._tblock , mode=Timer.ONE_SHOT, callback=self.cb)
            self._times[self.edge] = t
            self.edge += 1

class NEC_IR(IR_RX):
    def __init__(self, pin, callback, extended=True, *args):
        # Block lasts <= 80ms and has 68 edges
        tblock = 80 if extended else 73  # Allow for some tx tolerance (?)
        super().__init__(pin, 68, tblock, callback, *args)
        self._extended = extended
        self._addr = 0

    def decode(self, _):
        try:
            if self.edge > 68:
                raise RuntimeError(OVERRUN)
            width = ticks_diff(self._times[1], self._times[0])
            if width < 4000:  # 9ms leading mark for all valid data
                raise RuntimeError(BADSTART)
            width = ticks_diff(self._times[2], self._times[1])
            if width > 3000:  # 4.5ms space for normal data
                if self.edge < 68:  # Haven't received the correct number of edges
                    raise RuntimeError(BADBLOCK)
                # Time spaces only (marks are always 562.5µs)
                # Space is 1.6875ms (1) or 562.5µs (0)
                # Skip last bit which is always 1
                val = 0
                for edge in range(3, 68 - 2, 2):
                    val >>= 1
                    if ticks_diff(self._times[edge + 1], self._times[edge]) > 1120:
                        val |= 0x80000000
            elif width > 1700: # 2.5ms space for a repeat code. Should have exactly 4 edges.
                raise RuntimeError(REPEAT if self.edge == 4 else BADREP)  # Treat REPEAT as error.
            else:
                raise RuntimeError(BADSTART)
            addr = val & 0xff  # 8 bit addr
            cmd = (val >> 16) & 0xff
            if cmd != (val >> 24) ^ 0xff:
                raise RuntimeError(BADDATA)
            if addr != ((val >> 8) ^ 0xff) & 0xff:  # 8 bit addr doesn't match check
                if not self._extended:
                    raise RuntimeError(BADADDR)
                addr |= val & 0xff00  # pass assumed 16 bit address to callback
            self._addr = addr
        except RuntimeError as e:
            cmd = e.args[0]
            addr = self._addr if cmd == REPEAT else 0  # REPEAT uses last address
        self.edge = 0  # Set up for new data burst and run user callback
        self.callback(cmd, addr, 0, *self.args)


class SONY_IR(IR_RX):
    def __init__(self, pin, callback, bits=20, *args):
        # 20 bit block has 42 edges and lasts <= 39ms nominal. Add 4ms to time
        # for tolerances except in 20 bit case where timing is tight with a
        # repeat period of 45ms.
        t = int(3 + bits * 1.8) + (1 if bits == 20 else 4)
        super().__init__(pin, 2 + bits * 2, t, callback, *args)
        self._addr = 0
        self._bits = bits

    def decode(self, _):
        try:
            nedges = self.edge  # No. of edges detected
            self.verbose and print('nedges', nedges)
            if nedges > 42:
                raise RuntimeError(OVERRUN)
            bits = (nedges - 2) // 2
            if nedges not in (26, 32, 42) or bits > self._bits:
                raise RuntimeError(BADBLOCK)
            self.verbose and print('SIRC {}bit'.format(bits))
            width = ticks_diff(self._times[1], self._times[0])
            if not 1800 < width < 3000:  # 2.4ms leading mark for all valid data
                raise RuntimeError(BADSTART)
            width = ticks_diff(self._times[2], self._times[1])
            if not 350 < width < 1000:  # 600μs space
                raise RuntimeError(BADSTART)

            val = 0  # Data received, LSB 1st
            x = 2
            bit = 1
            while x < nedges - 2:
                if ticks_diff(self._times[x + 1], self._times[x]) > 900:
                    val |= bit
                bit <<= 1
                x += 2

            cmd = val & 0x7f  # 7 bit command
            val >>= 7
            if nedges < 42:
                addr = val & 0xff  # 5 or 8 bit addr
                val = 0
            else:
                addr = val & 0x1f  # 5 bit addr
                val >>= 5  # 8 bit extended
        except RuntimeError as e:
            cmd = e.args[0]
            addr = 0
            val = 0
        self.edge = 0  # Set up for new data burst and run user callback
        self.callback(cmd, addr, val, *self.args)

class RC5_IR(IR_RX):
    def __init__(self, pin, callback, *args):
        # Block lasts <= 30ms and has <= 28 edges
        super().__init__(pin, 28, 30, callback, *args)

    def decode(self, _):
        try:
            nedges = self.edge  # No. of edges detected
            if not 14 <= nedges <= 28:
                raise RuntimeError(OVERRUN if nedges > 28 else BADSTART)
            # Regenerate bitstream
            bits = 0
            bit = 1
            for x in range(1, nedges):
                width = ticks_diff(self._times[x], self._times[x - 1])
                if not 500 < width < 2000:
                    raise RuntimeError(BADBLOCK)
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
                    raise RuntimeError(BADBLOCK)
                v |= b0
                m0 >>= 2
                m1 >>= 2
            # Split into fields (val, addr, ctrl)
            val = (v & 0x3f) | (0x40 if ((v >> 12) & 1) else 0)
            addr = (v >> 6) & 0x1f
            ctrl = (v >> 11) & 1

        except RuntimeError as e:
            val, addr, ctrl = e.args[0], 0, 0
        self.edge = 0  # Set up for new data burst and run user callback
        self.callback(val, addr, ctrl, *self.args)

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
                raise RuntimeError(OVERRUN if nedges > 28 else BADSTART)
            for x, lims in enumerate(self.hdr):
                width = ticks_diff(self._times[x + 1], self._times[x])
                if not (lims[0] < width < lims[1]):
                    self.verbose and print('Bad start', x, width, lims)
                    raise RuntimeError(BADSTART)
            x += 1
            width = ticks_diff(self._times[x + 1], self._times[x])
            # 2nd bit of last 0 is 444μs (0) or 1333μs (1)
            if not 222 < width < 1555:
                self.verbose and print('Bad block 1 Width', width, 'x', x)
                raise RuntimeError(BADBLOCK)
            short = width < 889
            v = int(not short)
            bit = v
            bits = 1  # Bits decoded
            x += 1 + int(short)
            width = ticks_diff(self._times[x + 1], self._times[x])
            if not 222 < width < 1555:
                self.verbose and print('Bad block 2 Width', width, 'x', x)
                raise RuntimeError(BADBLOCK)
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
                    raise RuntimeError(BADBLOCK)
                # width is 444/889 nominal
                width = ticks_diff(self._times[x + 1], self._times[x])
                if not 222 < width < 1111:
                    self.verbose and print('Bad block 3 Width', width, 'x', x)
                    raise RuntimeError(BADBLOCK)
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
        self.edge = 0  # Set up for new data burst and run user callback
        self.callback(val, addr, ctrl, *self.args)
