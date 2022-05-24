# samsung.py Decoder for IR remote control using synchronous code
# Supports Samsung TV remote protocols.

# Author: J.E. Tannenbaum
# Copyright J.E.Tannenbaum 2021 Released under the MIT license

from utime import ticks_us, ticks_diff
from ir_rx import IR_RX

class SAMSUNG(IR_RX):
    def __init__(self, pin, callback, *args):
        super().__init__(pin, 68, 80, callback, *args)

    def decode(self, _):
        def near(v, target):
            return target * 0.8 < v < target * 1.2

        lb = self.edge - 1  # Possible length of burst
        burst = []
        for x in range(lb):
            dt = ticks_diff(self._times[x + 1], self._times[x])
            if x > 0 and dt > 10000:  # Reached gap between repeats
                break
            burst.append(dt)

        lb = len(burst)  # Actual length
        cmd = 0
        if near(burst[0], 4500) and near(burst[1], 4500) and lb == 67:
            # Skip the starting bits and the checksum at the end of the sequence
            for x in range(2, lb - 1, 2):
                cmd *= 2
                # Test for logical 1 (One byte low, next byte high)
                if burst[x] < 1000 and burst[x + 1] > 1000:
                    cmd += 1

        # Set up for new data burst and run user callback
        self.do_callback(cmd, 0, 0)
