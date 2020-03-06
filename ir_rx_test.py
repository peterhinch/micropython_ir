# ir_rx_test.py Test program for IR remote control decoder arem.py
# Supports Pyboard and ESP8266

# Author: Peter Hinch
# Copyright Peter Hinch 2020 Released under the MIT license

# Run this to characterise a remote.

from sys import platform
import time
import gc
from machine import Pin, freq
from ir_rx import *

ESP32 = platform == 'esp32' or platform == 'esp32_LoBo'

if platform == 'pyboard':
    p = Pin('X3', Pin.IN)
elif platform == 'esp8266':
    freq(160000000)
    p = Pin(13, Pin.IN)
elif ESP32:
    p = Pin(23, Pin.IN)  # was 27

# User callback
def cb(data, addr, ctrl):
    if data < 0:  # NEC protocol sends repeat codes.
        print('Repeat code.')
    else:
        print('Data {:03x} Addr {:03x} Ctrl {:01x}'.format(data, addr, ctrl))

# Optionally print debug information
def errf(data):
    errors = {BADSTART : 'Invalid start pulse', BADBLOCK : 'Error: bad block',
            BADREP : 'Error: repeat', OVERRUN : 'Error: overrun',
            BADDATA : 'Error: invalid data', BADADDR : 'Error: invalid address'}
    print(errors[data])

s = '''Test for IR receiver. Run:
from ir_rx_test import test
test() for NEC protocol,
test(1) for Sony SIRC 12 bit,
test(2) for Sony SIRC 15 bit,
test(3) for Sony SIRC 20 bit,
test(5) for Philips RC-5 protocol,
test(6) for RC6 mode 0.

Hit ctrl-c to stop, then ctrl-d to soft reset.'''

print(s)

def test(proto=0):
    if proto == 0:
        ir = NEC_IR(p, cb)  # Extended mode
    elif proto < 4:
        ir = SONY_IR(p, cb)
        ir.bits = (12, 15, 20)[proto - 1]
        #ir.verbose = True
    elif proto == 5:
        ir = RC5_IR(p, cb)
    elif proto == 6:
        ir = RC6_M0(p, cb)
    ir.error_function(errf)  # Show debug information
    # A real application would do something here...
    while True:
        print('running')
        time.sleep(5)
        gc.collect()
