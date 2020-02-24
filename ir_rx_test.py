# ir_rx_test.py Test program for IR remote control decoder arem.py
# Supports Pyboard and ESP8266

# Author: Peter Hinch
# Copyright Peter Hinch 2020 Released under the MIT license

# Run this to characterise a remote.

from sys import platform
import time
from machine import Pin, freq
from arem import *

ESP32 = platform == 'esp32' or platform == 'esp32_LoBo'

if platform == 'pyboard':
    p = Pin('X3', Pin.IN)
elif platform == 'esp8266':
    freq(160000000)
    p = Pin(13, Pin.IN)
elif ESP32:
    p = Pin(23, Pin.IN)

errors = {BADSTART : 'Invalid start pulse', BADBLOCK : 'Error: bad block',
          BADREP : 'Error: repeat', OVERRUN : 'Error: overrun',
          BADDATA : 'Error: invalid data', BADADDR : 'Error: invalid address'}

def cb(data, addr, ctrl):
    if data == REPEAT:  # NEC protocol sends repeat codes.
        print('Repeat code.')
    elif data >= 0:
        print('Data {:03x} Addr {:03x} Ctrl {:01x}'.format(data, addr, ctrl))
    else:
        print('{} Address: {}'.format(errors[data], hex(addr)))


s = '''Test for IR receiver. Run:
ir_tx_test.test() for NEC protocol,
ir_tx_test.test(5) for Philips RC-5 protocol,
ir_tx_test.test(6) for RC6 mode 0.

Background processing means REPL prompt reappears.
Hit ctrl-D to stop (soft reset).'''

print(s)

def test(proto=0):
    if proto == 0:
        ir = NEC_IR(p, cb, True, 0)  # Extended mode, dummy ctrl arg for callback
    elif proto == 5:
        ir = RC5_IR(p, cb)
    elif proto == 6:
        ir = RC6_M0(p, cb)
    # A real application would do something here...
    #while True:
        #time.sleep(5)
        #print('running')
