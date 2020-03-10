# __init__.py Nonblocking IR blaster
# Runs on Pyboard D or Pyboard 1.x (not Pyboard Lite) and ESP32

# Released under the MIT License (MIT). See LICENSE.

# Copyright (c) 2020 Peter Hinch
from sys import platform
ESP32 = platform == 'esp32' or platform == 'esp32_LoBo'
if ESP32:
    from machine import Pin, Timer, PWM, freq
else:
    from pyb import Pin, Timer  # Pyboard does not support machine.PWM

from micropython import const
from array import array
import micropython

# micropython.alloc_emergency_exception_buf(100)

# ABC only
_SPACE = const(0)
# If the wiring is such that 3.3V turns the LED off, set _SPACE as follows
# On Pyboard 100, on ESP32 1023
# Shared by NEC
STOP = const(0)  # End of data

# IR abstract base class. Array holds periods in μs between toggling 36/38KHz
# carrier on or off. Physical transmission occurs in an ISR context controlled
# by timer 2 and timer 5. See README.md for details of operation.
class IR:

    def __init__(self, pin, cfreq, asize, duty, verbose):
        if ESP32:
            freq(240000000)
            self._pwm = PWM(pin)  # Produces 36/38/40KHz carrier
            self._pwm.deinit()
            self._pwm.init(freq=cfreq, duty=_SPACE)
            # ESP32: 0 <= duty <= 1023
            self._duty = round((duty if not _SPACE else (100 - duty)) * 10.23)
            self._tim = Timer(-1)  # Controls carrier on/off times
            self._off = self.esp_off  # Turn IR LED off
            self._onoff = self.esp_onoff  # Set IR LED state and refresh timer
        else:  # Pyboard
            tim = Timer(2, freq=cfreq)  # Timer 2/pin produces 36/38/40KHz carrier
            self._ch = tim.channel(1, Timer.PWM, pin=pin)
            self._ch.pulse_width_percent(_SPACE)  # Turn off IR LED
            # Pyboard: 0 <= pulse_width_percent <= 100
            self._duty = duty if not _SPACE else (100 - duty)
            self._tim = Timer(5)  # Timer 5 controls carrier on/off times
            self._off = self.pb_off
            self._onoff = self.pb_onoff
        self._tcb = self.cb  # Pre-allocate
        self.verbose = verbose
        self.arr = array('H', 0 for _ in range(asize))  # on/off times (μs)
        self.carrier = False  # Notional carrier state while encoding biphase
        self.aptr = 0  # Index into array

    # Before populating array, zero pointer, set notional carrier state (off).
    def transmit(self, addr, data, toggle=0):  # NEC: toggle is unused
        self.aptr = 0  # Inital conditions for tx: index into array
        self.carrier = False
        self.tx(addr, data, toggle)
        self.append(STOP)
        self.aptr = 0  # Reset pointer
        self.cb(self._tim)  # Initiate physical transmission.

    # Turn IR LED off (pyboard and ESP32 variants)
    def pb_off(self):
        self._ch.pulse_width_percent(_SPACE)

    def esp_off(self):
        self._pwm.duty(_SPACE)

    # Turn IR LED on or off and re-initialise timer (pyboard and ESP32 variants)
    @micropython.native
    def pb_onoff(self, p, v):
        self._ch.pulse_width_percent(_SPACE if p & 1 else self._duty)
        self._tim.init(prescaler=84, period=v, callback=self._tcb)

    @micropython.native
    def esp_onoff(self, p, v):
        self._pwm.duty(_SPACE if p & 1 else self._duty)
        self._tim.init(mode=Timer.ONE_SHOT, freq=v, callback=self.cb)  

    def cb(self, t):  # T5 callback, generate a carrier mark or space
        t.deinit()
        p = self.aptr
        v = self.arr[p]
        if v == STOP:
            self._off()  # Turn off IR LED.
            return
        self._onoff(p, v)
        self.aptr += 1

    def append(self, *times):  # Append one or more time peiods to .arr
        for t in times:
            if ESP32 and t:
                t -= 350  # ESP32 sluggishness
                t = round(1_000_000 / t)  # Store in Hz
            self.arr[self.aptr] = t
            self.aptr += 1
            self.carrier = not self.carrier  # Keep track of carrier state
            self.verbose and print('append', t, 'carrier', self.carrier)

    def add(self, t):  # Increase last time value
        assert t > 0
        self.verbose and print('add', t)
        # .carrier unaffected
        if ESP32:
            t -= 350
            self.arr[self.aptr - 1] = round((self.arr[self.aptr - 1] / 1_000_000 + t) / 1_000_000)
        else:
            self.arr[self.aptr - 1] += t
