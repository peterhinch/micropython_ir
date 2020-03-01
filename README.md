# Device drivers for IR (infra red) remote controls

This repo provides a driver to receive from IR (infra red) remote controls and
a driver for IR "blaster" apps. The device drivers are nonblocking. They do not
require `uasyncio` but are compatible with it.

NOTE: The receiver is intended to be cross-platform. In testing it has proved
problematic on ESP8266 and ESP32 with a tendency to crash and reboot,
especially when repeated pulse trains re received. The cause is under
investigation.

# 1. IR communication

IR communication uses a carrier frequency to pulse the IR source. Modulation
takes the form of OOK (on-off keying). There are multiple protocols and at
least three options for carrier frequency, namely 36KHz, 38KHz and 40KHz.

The drivers support NEC and Sony protocols and two Philips protocols, namely
RC-5 and RC-6 mode 0. In the case of the transmitter the carrier frequency is a
runtime parameter: any value may be specified. The receiver uses a hardware
demodulator which should be specified for the correct frequency. The receiver
device driver sees the demodulated signal and is hence carrier frequency
agnostic.

Examining waveforms from various remote controls it is evident that numerous
protocols exist. Some are doubtless proprietary and undocumented. The supported
protocols are those for which I managed to locate documentation. My preference
is for the NEC version. It has conservative timing and ample scope for error
detection. RC-5 has limited error detection, and RC-6 mode 0 has rather fast
timing: I doubt that detection can be accomplished on targets slower than a
Pyboard.

A remote using the NEC protocol is [this one](https://www.adafruit.com/products/389).

Remotes transmit an address and a data byte, plus in some cases an extra value.
The address denotes the physical device being controlled. The data defines the
button on the remote. Provision usually exists for differentiating between a
button repeatedly pressed and one which is held down; the mechanism is protocol
dependent.

# 2. Hardware Requirements

The receiver is cross-platform. It requires an IR receiver chip to demodulate
the carrier. The chip must be selected for the frequency in use by the remote.
For 38KHz devices a receiver chip such as the Vishay TSOP4838 or the
[adafruit one](https://www.adafruit.com/products/157) is required. This
demodulates the 38KHz IR pulses and passes the demodulated pulse train to the
microcontroller. The tested chip returns a 0 level on carrier detect, but the
driver design ensures operation regardless of sense.

In my testing a 38KHz demodulator worked with 36KHz and 40KHz remotes, but this
is obviously not guaranteed or optimal.

The pin used to connect the decoder chip to the target is arbitrary. The test
program assumes pin X3 on the Pyboard, pin 23 on ESP32 and pin 13 on ESP8266.
On the WeMos D1 Mini the equivalent pin is D7.

The transmitter requires a Pyboard 1.x (not Lite) or a Pyboard D. Output is via
an IR LED which will normally need a transistor to provide sufficient current.
Typically these need 50-100mA of drive to achieve reasonable range and data
integrity. A suitable LED is [this one](https://www.adafruit.com/product/387).

The transmitter test script assumes pin X1 for IR output. It can be changed,
but it must support Timer 2 channel 1. Pins for pushbutton inputs are
arbitrary: X3 and X4 are used.

# 3. Installation

On import, demos print an explanation of how to run them.

## 3.1 Receiver

Copy the following files to the target filesystem:
 1. `ir_rx.py` The receiver device driver.
 2. `ir_rx_test.py` Demo of a receiver.

There are no dependencies.

The demo can be used to characterise IR remotes. It displays the codes returned
by each button. This can aid in the design of receiver applications. When the
demo runs, the REPL prompt reappears: this is because it sets up an ISR context
and returns. Press `ctrl-d` to cancel it. A real application would run code
after initialising reception so this behaviour would not occur.

## 3.2 Transmitter

Copy the following files to the Pyboard filesystem:
 1. `ir_tx.py` The transmitter device driver.
 2. `ir_tx_test.py` Demo of a 2-button remote controller.

The device driver has no dependencies. The test program requires `uasyncio`
from the official library and `aswitch.py` from
[this repo](https://github.com/peterhinch/micropython-async).

# 4. Receiver

This implements a class for each supported protocol, namely `NEC_IR`,
`SONY_IR`, `RC5_IR` and `RC6_M0`. Applications should instantiate the
appropriate class with a callback. The callback will run whenever an IR pulse
train is received.

Constructor:  
`NEC_IR` args: `pin`, `callback`, `extended=True`, `*args`  
`SONY_IR` args: `pin`, `callback`, `bits=20`, `*args`  
`RC5_IR` and `RC6_M0`: args `pin`, `callback`, `*args`  

Args (all protocols):  
 1. `pin` is a `machine.Pin` instance configured as an input, connected to the
 IR decoder chip.  
 2. `callback` is the user supplied callback (see below).
 4. `*args` Any further args will be passed to the callback.  

Protocol specific args:
 1. `extended` is an NEC specific boolean. Remotes using the NEC protocol can
 send 8 or 16 bit addresses. If `True` 16 bit addresses are assumed - an 8 bit
 address will be correctly received. Set `False` to enable extra error checking
 for remotes that return an 8 bit address.
 2. `bits=20` Sony specific. The SIRC protocol comes in 3 variants: 12, 15 and
 20 bits. The default will handle bitstreams from all three types of remote. A
 value matching your remote improves the timing and reduces the  likelihood of
 errors when handling repeats: in 20-bit mode SIRC timing when a button is held
 down is tight. A worst-case 20-bit block takes 39ms nominal, yet the repeat
 time is 45ms nominal.  
 The Sony remote tested issues both 12 bit and 15 bit streams.

The callback takes the following args:  
 1. `data` Integer value fom the remote. A negative value indicates an error
 except for the value of -1 which signifies an NEC repeat code (see below).
 2. `addr` Address from the remote
 3. `ctrl` 0 in the case of NEC. Philips protocols toggle this bit on repeat
 button presses. If the button is held down the bit is not toggled. The
 transmitter demo implements this behaviour.  
 In the case of Sony the value will be 0 unless receiving a 20-bit stream, in
 which case it will hold the extended value.
 4. Any args passed to the constructor.

Class variable:  
 1. `verbose=False` If `True` emits debug output.

# 4.1 Errors

IR reception is inevitably subject to errors, notably if the remote is operated
near the limit of its range, if it is not pointed at the receiver or if its
batteries are low. So applications must check for, and usually ignore, errors.
These are flagged by data values < `REPEAT` (-1).

On the ESP8266 there is a further source of errors. This results from the large
and variable interrupt latency of the device which can exceed the pulse
duration. This causes pulses to be missed. This tendency is slightly reduced by
running the chip at 160MHz.

In general applications should provide user feedback of correct reception.
Users tend to press the key again if the expected action is absent.

Data values passed to the callback are zero or positive. Negative values
indicate a repeat code or an error.

`REPEAT` A repeat code was received.

Any data value < `REPEAT` denotes an error. In general applications do not
need to decode these, but they may be of use in debugging. For completeness
they are listed below.

`BADSTART` A short (<= 4ms) start pulse was received. May occur due to IR
interference, e.g. from fluorescent lights. The TSOP4838 is prone to producing
200µs pulses on occasion, especially when using the ESP8266.  
`BADBLOCK` A normal data block: too few edges received. Occurs on the ESP8266
owing to high interrupt latency.  
`BADREP` A repeat block: an incorrect number of edges were received.  
`OVERRUN` A normal data block: too many edges received.  
`BADDATA` Data did not match check byte.  
`BADADDR` Where `extended` is `False` the 8-bit address is checked
against the check byte. This code is returned on failure.  

# 4.2 Receiver platforms

The NEC protocol has been tested against Pyboard, ESP8266 and ESP32 targets.
The Philips protocols - especially RC-6 - have tighter timing constraints. I
have not yet tested these, but I anticipate problems.

# 4.3 Principle of operation

Protocol classes inherit from the abstract base class `IR_RX`. This uses a pin
interrupt to store in an array the start and end times of pulses (in μs).
Arrival of the first pulse triggers a software timer which runs for the
expected duration of an IR block (`tblock`). When it times out its callback
(`.decode`) decodes the data and calls the user callback. The use of a software
timer ensures that `.decode` and the user callback can allocate.

The size of the array and the duration of the timer are protocol dependent and
are set by the subclasses. The `.decode` method is provided in the subclass.

CPU times used by `.decode` (not including the user callback) were measured on
a Pyboard D SF2W at stock frequency. They were NEC 1ms for normal data, 100μs
for a repeat code. Philips codes: RC-5 900μs, RC-6 mode 0 5.5ms.

# 5 Transmitter

This is specific to Pyboard D and Pyboard 1.x (not Lite).

It implements a class for each supported protocol, namely `NEC`, `SONY`, `RC5`
and `RC6_M0`. The application instantiates the appropriate class and calls the
`transmit` method to send data.

Constructor  
All constructors take the following args:  
 1. `pin` An initialised `pyb.Pin` instance supporting Timer 2 channel 1: `X1`
 is employed by the test script. Must be connected to the IR diode as described
 below.
 2. `freq=default` The carrier frequency in Hz. The default for NEC is 38000,
 Sony is 40000 and Philips is 36000.
 3. `verbose=False` If `True` emits debug output.

The `SONY` constructor is of form `pin, bits=12, freq=40000, verbose=False`.
The `bits` value may be 12, 15 or 20 to set SIRC variant in use. Other args are
as above.

Method:
 1. `transmit(addr, data, toggle=0)` Integer args. `addr` and `data` are
 normally 8-bit values and `toggle` is normally 0 or 1.  
 In the case of NEC, if an address < 256 is passed, normal mode is assumed and
 the complementary value is appended. 16-bit values are transmitted as extended
 addresses.  
 In the case of NEC the `toggle` value is ignored. For Philips protocols it
 should be toggled each time a button is pressed, and retained if the button is
 held down. The test program illustrates a way to do this.  
 `SONY` ignores `toggle` unless in 20-bit mode, in which case it is transmitted
 as the `extended` value and can be any integer in range 0 to 255.

The `transmit` method is synchronous with rapid return. Actual transmission
occurs as a background process, controlled by timers 2 and 5. Execution times
on a Pyboard 1.1 were 3.3ms for NEC, 1.5ms for RC5 and 2ms for RC6.

# 5.1 Wiring

I use the following circuit which delivers just under 40mA to the diode. R2 may
be reduced for higher current.  
![Image](images/circuit.png)

This alternative delivers a constant current of about 53mA if a higher voltage
than 5V is available. R4 determines the current value and may be reduced to
increase power.  
![Image](images/circuit2.png)

The transistor type is not critical.

The driver assumes circuits as shown. Here the carrier "off" state is 0V,
which is the driver default. If using a circuit where "off" is required to be
3.3V, the constant `_SPACE` in `ir_tx.py` should be changed to 100.

# 5.2 Principle of operation

The classes inherit from the abstract base class `IR`. This has an array `.arr`
to contain the duration (in μs) of each carrier on or off period. The
`transmit` method calls a `tx` method of the subclass which populates this
array. On completion `transmit` appends a special `STOP` value and initiates
physical transmission which occurs in an interrupt context.

This is performed by two hardware timers initiated in the constructor. Timer 2,
channel 1 is used to configure the output pin as a PWM channel. Its frequency
is set in the constructor. The OOK is performed by dynamically changing the
duty ratio using the timer channel's `pulse_width_percent` method: this varies
the pulse width from 0 to a duty ratio passed to the constructor. The NEC
protocol defaults to 50%, the Sony and Philips ones to 30%.

The duty ratio is changed by the Timer 5 callback `._cb`. This retrieves the
next duration from the array. If it is not `STOP` it toggles the duty cycle
and re-initialises T5 for the new duration.

The `IR.append` enables times to be added to the array, keeping track of the
notional carrier on/off state for biphase generation. The `IR.add` method
facilitates lengthening a pulse as required in the biphase sequences used in
Philips protocols.

# 6. References

[General information about IR](https://www.sbprojects.net/knowledge/ir/)

The NEC protocol:  
[altium](http://techdocs.altium.com/display/FPGA/NEC+Infrared+Transmission+Protocol)  
[circuitvalley](http://www.circuitvalley.com/2013/09/nec-protocol-ir-infrared-remote-control.html)

Philips protocols:  
[RC5](https://en.wikipedia.org/wiki/RC-5)  
[RC6](https://www.sbprojects.net/knowledge/ir/rc6.php)

Sony protocol:  
[SIRC](https://www.sbprojects.net/knowledge/ir/sirc.php)

# Appendix 1 NEC Protocol description

A normal burst comprises exactly 68 edges, the exception being a repeat code
which has 4. An incorrect number of edges is treated as an error. All bursts
begin with a 9ms pulse. In a normal code this is followed by a 4.5ms space; a
repeat code is identified by a 2.25ms space. A data burst lasts for 67.5ms.

Data bits comprise a 562.5µs mark followed by a space whose length determines
the bit value. 562.5µs denotes 0 and 1.6875ms denotes 1.

In 8 bit address mode the complement of the address and data values is sent to
provide error checking. This also ensures that the number of 1's and 0's in a
burst is constant, giving a constant burst length of 67.5ms. In extended
address mode this constancy is lost. The burst length can (by my calculations)
run to 76.5ms.

A pin interrupt records the time of every state change (in µs). The first
interrupt in a burst sets an event, passing the time of the state change. A
coroutine waits on the event, yields for the duration of a data burst, then
decodes the stored data before calling the user-specified callback.

Passing the time to the `Event` instance enables the coro to compensate for
any asyncio latency when setting its delay period.

The algorithm promotes interrupt handler speed over RAM use: the 276 bytes used
for the data array could be reduced to 69 bytes by computing and saving deltas
in the interrupt service routine.
