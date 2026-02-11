# Decoder for OpenLASIR IR protocol.
# Similar to NEC Extended, but error checking is on the address (first 8 bits inverted 
# in second 8 bits) instead of on the command, giving an 8-bit validated address and 
# 16-bit command.
# Full protocol spec: https://github.com/danielweidman/OpenLASIR

# Strongly based on NEC decoder by Peter Hinch (MIT license)
from utime import ticks_us, ticks_diff
from ir_rx import IR_RX


class OpenLASIR(IR_RX):
    def __init__(self, pin, callback, *args):
        # Block lasts <= 80ms and has 68 edges
        super().__init__(pin, 68, 80, callback, *args)
        self._addr = 0

    def decode(self, _):
        try:
            if self.edge > 68:
                raise RuntimeError(self.OVERRUN)
            width = ticks_diff(self._times[1], self._times[0])
            if width < 4000:  # 9ms leading mark for all valid data
                raise RuntimeError(self.BADSTART)
            width = ticks_diff(self._times[2], self._times[1])
            if width > 3000:  # 4.5ms space for normal data
                if self.edge < 68:  # Haven't received the correct number of edges
                    raise RuntimeError(self.BADBLOCK)
                # Time spaces only (marks are always 562.5us)
                # Space is 1.6875ms (1) or 562.5us (0)
                # Skip last bit which is always 1
                val = 0
                for edge in range(3, 68 - 2, 2):
                    val >>= 1
                    if ticks_diff(self._times[edge + 1], self._times[edge]) > 1120:
                        val |= 0x80000000
            elif width > 1700:  # 2.5ms space for a repeat code
                raise RuntimeError(self.REPEAT if self.edge == 4 else self.BADREP)
            else:
                raise RuntimeError(self.BADSTART)
            addr = val & 0xff  # First 8 bits of address
            # Error check: second 8 bits must be the inverted first 8 bits
            if addr != ((val >> 8) ^ 0xff) & 0xff:
                raise RuntimeError(self.BADADDR)
            # Command is full 16 bits with no error check
            cmd = (val >> 16) & 0xffff
            self._addr = addr
        except RuntimeError as e:
            cmd = e.args[0]
            addr = self._addr if cmd == self.REPEAT else 0
        # Set up for new data burst and run user callback
        self.do_callback(cmd, addr, 0, self.REPEAT)
