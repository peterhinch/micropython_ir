# Encoder for OpenLASIR IR protocol.
# Similar to NEC Extended, but error checking is on the address (first 8 bits inverted 
# in second 8 bits) instead of on the command, giving an 8-bit validated address and 
# 16-bit command.
# Full protocol spec: https://github.com/danielweidman/OpenLASIR

# Strongly based on NEC encoder by Peter Hinch (MIT license)
from micropython import const
from ir_tx import IR, STOP

_TBURST = const(563)
_T_ONE = const(1687)


class OpenLASIR(IR):
    valid = (0xff, 0xffff, 0)  # Max addr (8-bit), data (16-bit), toggle

    def __init__(self, pin, freq=38000, verbose=False):
        super().__init__(pin, freq, 68, 33, verbose)  # Measured duty ratio 33%

    def _bit(self, b):
        self.append(_TBURST, _T_ONE if b else _TBURST)

    def tx(self, addr, data, _):  # Ignore toggle
        self.append(9000, 4500)
        # Address: 8-bit with inverted complement for error checking
        addr &= 0xff
        addr |= ((addr ^ 0xff) << 8)
        for _ in range(16):
            self._bit(addr & 1)
            addr >>= 1
        # Data/command: 16-bit, sent as-is with no error checking
        for _ in range(16):
            self._bit(data & 1)
            data >>= 1
        self.append(_TBURST)

    def repeat(self):
        self.aptr = 0
        self.append(9000, 2250, _TBURST)
        self.trigger()  # Initiate physical transmission.
