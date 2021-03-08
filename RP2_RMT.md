# 1. Pulse train ouput on RP2

The `RP2_RMT` class provides functionality similar to that of the ESP32 `RMT`
class. It enables pulse trains to be output using a non-blocking driver. By
default the train occurs once. Alternatively it can repeat a defned number of
times, or can be repeated continuously.

The class was designed for my [IR blaster](https://github.com/peterhinch/micropython_ir)
and [433MHz remote](https://github.com/peterhinch/micropython_remote)
libraries. It supports an optional carrier frequency, where each high pulse can
appear as a burst of a defined carrier frequency. The class can support both
forms concurrently on a pair of pins: one pin produces pulses while a second
produces carrier bursts.

Pulse trains are specified as arrays with each element being a duration in μs.
Arrays may be of integers or half-words depending on the range of times to be
covered. The duration of a "tick" is 1μs by default, but this can be changed.

# 2. The RP2_RMT class

## 2.1 Constructor

This takes the following args:
 1. `pin_pulse=None` If an ouput `Pin` instance is provided, pulses will be
 output on it.
 2. `carrier=None` To output a carrier, a 3-tuple should be provided comprising
 `(pin, freq, duty)` where `pin` is an output pin instance, `freq` is the
 carrier frequency in Hz and `duty` is the duty ratio in %.
 3. `sm_no=0` State machine no.
 4. `sm_freq=1_000_000` Clock frequency for SM. Defines the unit for pulse
 durations.

## 2.2 Methods

### 2.2.1 send

This returns "immediately" with a pulse train being emitted as a background
process. Args:
 1. `ar` A zero terminated array of pulse durations in μs. See notes below.
 2. `reps=1` No. of repetions. 0 indicates continuous output.
 3. `check=True` By default ensures that the pulse train ends in the inactive
 state.

In normal operation, between pulse trains, the pulse pin is low and the carrier
is off. A pulse train ends when a 0 pulse width is encountered: this allows
pulse trains to be shorter than the array length, for example where a
pre-allocated array stores pulse trains of varying lengths. In RF transmitter
applications ensuring the carrier is off between pulse trains may be a legal
requirement, so by default the `send` method enforces this.

The first element of the array defines the duration of the first high going
pulse, with the second being the duration of the first `off` period. If there
are an even number of elements prior to the terminating 0, the signal will end
in the `off` state. If the `check` arg is `True`, `.send()` will check for an
odd number of elements; in this case it will overwrite the last element with 0
to enforce a final `off` state.

This check may be skipped by setting `check=False`. This provides a means of
inverting the normal sense of the driver: if the first pulse train has an odd
number of elements and `check=False` the pin will be left high (and the carrier
on). Subsequent normal pulsetrains will start and end in the high state.

### 2.2.2 busy

No args. Returns `True` if a pulse train is being emitted.

### 2.2.3 cancel

No args. If a pulse train is being emitted it will continue to the end but no
further repetitions will take place.

# 3. Design

The class constructor installs one of two PIO scripts depending on whether a
`pin_pulse` is specified. If it is, the `pulsetrain` script is loaded which
drives the pin directly from the PIO. If no `pin_pulse` is required, the
`irqtrain` script is loaded. Both scripts cause an IRQ to be raised at times
when a pulse would start or end.

The `send` method loads the transmit FIFO with initial pulse durations and
starts the state machine. The `._cb` ISR keeps the FIFO loaded with data until
a 0 entry is encountered. It also turns the carrier on and off (using a PWM
instance). This means that there is some latency between the pulse and the
carrier. However latencies at start and end are effectively identical, so the
duration of a carrier burst is correct.

# 4. Limitations

While the tick interval can be reduced to provide timing precision better than
1μs, the design of this class will not support very high pulse repetition
frequencies. This is because each pulse causes an interrupt: MicroPython is
unable to support high IRQ rates.
[This library](https://github.com/robert-hh/RP2040-Examples/tree/master/pulses)
is more capable in this regard.
