# ir_tx.py Nonblocking IR blaster
# Runs on Pyboard D or Pyboard 1.x only (not Pyboard Lite)

# Released under the MIT License (MIT). See LICENSE.

# Copyright (c) 2020 Peter Hinch

from pyb import Pin, Timer
from time import sleep_us, sleep
from micropython import const
from array import array
import micropython

# micropython.alloc_emergency_exception_buf(100)

# Common
_SPACE = const(0)  # Or 100. Depends on wiring: 0 assumes logic 0 turns IR off.
_STOP = const(0)  # End of data
# NEC
_TBURST = const(563)
_T_ONE = const(1687)
# RC5
_T_RC5 = const(889)  # Time for pulse of carrier
# RC6_M0
_T_RC6 = const(444)
_T2_RC6 = const(889)

# IR abstract base class. Array holds periods in μs between toggling 36/38KHz
# carrier on or off.
# Subclass is responsible for populating .arr and initiating transmission.
# Operation is in two phases: .transmit populates .arr with times in μs, then
# calls .start to initiate physical transmission.
class IR:

    def __init__(self, pin, freq, asize, duty):
        tim = Timer(2, freq=freq)
        self._ch = tim.channel(1, Timer.PWM, pin=pin)
        self._ch.pulse_width_percent(_SPACE)
        self.duty = duty
        self.arr = array('H', 0 for _ in range(asize))
        self._tim = Timer(5)
        self._tcb = self._cb
        self.pretrans()

    # Before populating array, zero pointer, set notional carrier state (off).
    def pretrans(self):
        self.aptr = 0  # Index into array
        self.carrier = False

    def start(self):
        self.aptr = 0  # Reset pointer and initiate TX.
        self._cb(self._tim)

    def _cb(self, t):
        t.deinit()
        p = self.aptr
        v = self.arr[p]
        if v == _STOP:
            self._ch.pulse_width_percent(_SPACE)  # Turn off IR LED.
            return
        self._ch.pulse_width_percent(_SPACE if p & 1 else self.duty)
        self._tim.init(prescaler=84, period=v, callback=self._tcb)
        self.aptr += 1

    def append(self, *times):  # Append one or more time peiods to .arr
        for t in times:
            self.arr[self.aptr] = t
            self.aptr += 1
            self.carrier = not self.carrier  # Keep track of carrier state
            print('append', t, 'carrier', self.carrier)

    def add(self, t):  # Increase last time value
        print('add', t)
        self.arr[self.aptr - 1] += t  # Carrier unaffected

# NEC protocol
class NEC(IR):

    def __init__(self, pin, freq=38000):  # NEC specifies 38KHz
        super().__init__(pin, freq, 68, 50)

    def _bit(self, b):
        self.append(_TBURST, _T_ONE if b else _TBURST)

    def transmit(self, addr, data, _=0):  # Ignore toggle if passed
        self.pretrans()  # Set initial conditions
        self.append(9000, 4500)
        if addr < 256:  # Short address: append complement
            addr |= ((addr ^ 0xff) << 8)
        for x in range(16):
            self._bit(addr & 1)
            addr >>= 1
        data |= ((data ^ 0xff) << 8)
        for x in range(16):
            self._bit(data & 1)
            data >>= 1
        self.append(_TBURST, _STOP)
        self.start()

    def repeat(self):
        self.aptr = 0
        self.append(9000, 2250, _TBURST, _STOP)


# Philips RC5 protocol
class RC5(IR):

    def __init__(self, pin, freq=36000):
        super().__init__(pin, freq, 28, 30)

    def transmit(self, addr, data, toggle):
        self.pretrans()  # Set initial conditions
        d = (data & 0x3f) | ((addr & 0x1f) << 6) | ((data & 0x40) << 6) | ((toggle & 1) << 11)
        print(bin(d))
        mask = 0x2000
        while mask:
            if mask == 0x2000:
                self.append(_T_RC5)
            else:
                bit = bool(d & mask)
                if bit ^ self.carrier:
                    self.add(_T_RC5)
                    self.append(_T_RC5)
                else:
                    self.append(_T_RC5, _T_RC5)
            mask >>= 1
        self.append(_STOP)
        self.start()

# Philips RC6 mode 0 protocol
class RC6_M0(IR):

    def __init__(self, pin, freq=36000):
        super().__init__(pin, freq, 44, 30)

    def transmit(self, addr, data, toggle):
        self.pretrans()  # Set initial conditions
        # leader, 1, 0, 0, 0
        self.append(2666, _T2_RC6, _T_RC6, _T2_RC6, _T_RC6, _T_RC6, _T_RC6, _T_RC6, _T_RC6)
        # Append a single bit of twice duration
        if toggle:
            self.add(_T2_RC6)
            self.append(_T2_RC6)
        else:
            self.append(_T2_RC6, _T2_RC6)
        d = (data & 0xff) | ((addr & 0xff) << 8)
        mask = 0x8000
        print('toggle', toggle, self.carrier, bool(d & mask))
        while mask:
            bit = bool(d & mask)
            if bit ^ self.carrier:
                self.append(_T_RC6, _T_RC6)
            else:
                self.add(_T_RC6)
                self.append(_T_RC6)
            mask >>= 1
        self.append(_STOP)
        self.start()
