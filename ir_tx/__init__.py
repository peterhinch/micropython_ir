# __init__.py Nonblocking IR blaster
# Runs on Pyboard D or Pyboard 1.x (not Pyboard Lite) and ESP32

# Released under the MIT License (MIT). See LICENSE.

# Copyright (c) 2020 Peter Hinch
from sys import platform
ESP32 = platform == 'esp32'  # Loboris not supported owing to RMT
if ESP32:
    from machine import Pin, PWM
    from esp32 import RMT
else:
    from pyb import Pin, Timer  # Pyboard does not support machine.PWM

from micropython import const
from array import array
import micropython

# micropython.alloc_emergency_exception_buf(100)

# Duty ratio in carrier off state.
_SPACE = const(0)
# On ESP32 gate hardware design is led_on = rmt and carrier

# Shared by NEC
STOP = const(0)  # End of data

# IR abstract base class. Array holds periods in μs between toggling 36/38KHz
# carrier on or off. Physical transmission occurs in an ISR context controlled
# by timer 2 and timer 5. See README.md for details of operation.
class IR:
    active_high = True  # Hardware turns IRLED on if pin goes high.

    def __init__(self, pin, cfreq, asize, duty, verbose):
        if not IR.active_high:
             duty = 100 - duty
        if ESP32:
            self._pwm = PWM(pin[0])  # Continuous 36/38/40KHz carrier
            self._pwm.deinit()
            # ESP32: 0 <= duty <= 1023
            self._pwm.init(freq=cfreq, duty=round(duty * 10.23))
            self._rmt = RMT(0, pin=pin[1], clock_div=80)  # 1μs resolution
        else:  # Pyboard
            tim = Timer(2, freq=cfreq)  # Timer 2/pin produces 36/38/40KHz carrier
            self._ch = tim.channel(1, Timer.PWM, pin=pin)
            self._ch.pulse_width_percent(_SPACE)  # Turn off IR LED
            # Pyboard: 0 <= pulse_width_percent <= 100
            self._duty = duty
            self._tim = Timer(5)  # Timer 5 controls carrier on/off times
        self._tcb = self._cb  # Pre-allocate
        self._arr = array('H', 0 for _ in range(asize))  # on/off times (μs)
        self._mva = memoryview(self._arr)
        # Subclass interface
        self.verbose = verbose
        self.carrier = False  # Notional carrier state while encoding biphase
        self.aptr = 0  # Index into array

    def _cb(self, t):  # T5 callback, generate a carrier mark or space
        t.deinit()
        p = self.aptr
        v = self._arr[p]
        if v == STOP:
            self._ch.pulse_width_percent(_SPACE)  # Turn off IR LED.
            return
        self._ch.pulse_width_percent(_SPACE if p & 1 else self._duty)
        self._tim.init(prescaler=84, period=v, callback=self._tcb)
        self.aptr += 1

    # Public interface
    # Before populating array, zero pointer, set notional carrier state (off).
    def transmit(self, addr, data, toggle=0):  # NEC: toggle is unused
        self.aptr = 0  # Inital conditions for tx: index into array
        self.carrier = False
        self.tx(addr, data, toggle)  # Subclass populates ._arr
        self.trigger()  # Initiate transmission

    # Subclass interface
    def trigger(self):  # Used by NEC to initiate a repeat frame
        if ESP32:
            self._rmt.write_pulses(tuple(self._mva[0 : self.aptr]), start = 1)
        else:
            self.append(STOP)
            self.aptr = 0  # Reset pointer
            self._cb(self._tim)  # Initiate physical transmission.

    def append(self, *times):  # Append one or more time peiods to ._arr
        for t in times:
            self._arr[self.aptr] = t
            self.aptr += 1
            self.carrier = not self.carrier  # Keep track of carrier state
            self.verbose and print('append', t, 'carrier', self.carrier)

    def add(self, t):  # Increase last time value (for biphase)
        assert t > 0
        self.verbose and print('add', t)
        # .carrier unaffected
        self._arr[self.aptr - 1] += t
