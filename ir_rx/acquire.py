# acquire.py Acquire a pulse train from an IR remote
# Supports NEC protocol.
# For a remote using NEC see https://www.adafruit.com/products/389

# Author: Peter Hinch
# Copyright Peter Hinch 2020 Released under the MIT license

from machine import Pin, freq
from sys import platform

from utime import sleep_ms, ticks_us, ticks_diff
from ir_rx import IR_RX


class IR_GET(IR_RX):
    def __init__(self, pin, nedges=100, twait=100, display=True):
        self.display = display
        super().__init__(pin, nedges, twait, lambda *_ : None)
        self.data = None

    def decode(self, _):
        def near(v, target):
            return target * 0.8 < v < target * 1.2
        nedges = self.edge
        if nedges < 4:
            return  # Noise
        burst = []
        duration = ticks_diff(self._times[0], self._times[nedges])  # 24892 for RC-5 22205 for RC-6
        for x in range(nedges - 1):
            dt = ticks_diff(self._times[x + 1], self._times[x])
            if x > 0 and dt > 10000:  # Reached gap between repeats
                break
            burst.append(dt)

        if self.display:
            detected = False
            for x, e in enumerate(burst):
                print('{:03d} {:5d}'.format(x, e))
            print()
            if burst[0] > 5000:
                print('NEC')
                detected = True
            elif burst[0] > 2000:  # Sony or Philips RC-6
                if burst[1] > 750:  # Probably Philips
                    if min(burst) < 600:
                        print('Philips RC-6 mode 0')
                        detected = True
                else:
                    lb = len(burst)
                    try:
                        nbits = {25:12, 31:15, 41:20}[len(burst)]
                    except IndexError:
                        pass
                    else:
                        detected = True
                    if detected:
                        print('Sony {}bit'.format(nbits))

            elif burst[0] < 1200:
                print('Philips RC-5')
                detected = True
            if not detected:
                print('Unknown protocol')

            print()
        self.data = burst
        # Set up for new data burst. Run null callback
        self.do_callback(0, 0, 0)

    def acquire(self):
        while self.data is None:
            sleep_ms(5)
        self.close()
        return self.data

def test():
    # Define pin according to platform
    if platform == 'pyboard':
        pin = Pin('X3', Pin.IN)
    elif platform == 'esp8266':
        freq(160000000)
        pin = Pin(13, Pin.IN)
    elif platform == 'esp32' or platform == 'esp32_LoBo':
        pin = Pin(23, Pin.IN)
    irg = IR_GET(pin)
    print('Waiting for IR data...')
    irg.acquire()

#          RC          Python   Calculated
# NEC      66          66       66
# Sony 12: 24       24       26 (2 hdr + 2*(7 data + 5 addr)  RC issues another: detect 26ms gap
# Sony 15: 75          30
# Sony 20  n/a         40

# Yamaha NEC 
# Pi/Vista MCE RC6 mode 0 Din't receive
# Panasonic TV recorder RC6 mode 0 Didn't receive
# Virgin RC-5 Receive OK
# Samsung TV RC6 mode 0  Didn't receive
