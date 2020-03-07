# Device drivers for IR (infra red) remote controls

This repo provides a driver to receive from IR (infra red) remote controls and
a driver for IR "blaster" apps. The device drivers are nonblocking. They do not
require `uasyncio` but are compatible with it.

The transmitter driver is specific to the Pyboard. The receiver is cross
platform and has been tested on Pyboard, ESP8266 and ESP32. See
[Receiver platforms](./README.md#42-receiver-platforms) for test results and
limitations.

# 1. IR communication

IR communication uses a carrier frequency to pulse the IR source. Modulation
takes the form of OOK (on-off keying). There are multiple protocols and at
least three options for carrier frequency, namely 36KHz, 38KHz and 40KHz.

The drivers support NEC and Sony protocols and two Philips protocols, namely
RC-5 and RC-6 mode 0. In the case of the transmitter the carrier frequency is a
runtime parameter: any value may be specified. The receiver uses a hardware
demodulator which should be purchased for the correct frequency. The receiver
device driver sees the demodulated signal and is hence carrier frequency
agnostic.

Examining waveforms from various remote controls it is evident that numerous
protocols exist. Some are doubtless proprietary and undocumented. The supported
protocols are those for which I managed to locate documentation. My preference
is for the NEC version. It has conservative timing and ample scope for error
detection. RC-5 has limited error detection, and RC-6 mode 0 has rather fast
timing.

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
is obviously neither guaranteed nor optimal.

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

This is a Python package. This minimises RAM usage: applications only import
the device driver for the protocol in use.

Copy the following to the target filesystem:
 1. `ir_rx` Directory and contents. Contains the device drivers.
 2. `ir_rx_test.py` Demo of a receiver.

There are no dependencies.

The demo can be used to characterise IR remotes. It displays the codes returned
by each button. This can aid in the design of receiver applications. The demo
prints "running" every 5 seconds and reports any data received from the remote.

## 3.2 Transmitter

Copy the following files to the Pyboard filesystem:
 1. `ir_tx.py` The transmitter device driver.
 2. `ir_tx_test.py` Demo of a 2-button remote controller.

The device driver has no dependencies. The test program requires `uasyncio`
from the official library and `aswitch.py` from
[this repo](https://github.com/peterhinch/micropython-async).

# 4. Receiver

This implements a class for each supported protocol. Applications should
instantiate the appropriate class with a callback. The callback will run
whenever an IR pulse train is received. Example running on a Pyboard:

```python
import time
from machine import Pin
from pyb import LED
from ir_rx.nec import NEC_8  # NEC remote, 8 bit addresses

red = LED(1)

def callback(data, addr, ctrl):
    if data < 0:  # NEC protocol sends repeat codes.
        print('Repeat code.')
    else:
        print('Data {:02x} Addr {:04x}'.format(data, addr))

ir = NEC_8(Pin('X3', Pin.IN), callback)
while True:
    time.sleep_ms(500)
    red.toggle()
```

#### Common to all classes

Constructor:  
Args:  
 1. `pin` is a `machine.Pin` instance configured as an input, connected to the
 IR decoder chip.  
 2. `callback` is the user supplied callback.
 3. `*args` Any further args will be passed to the callback.  

The user callback takes the following args:  
 1. `data` (`int`) Value from the remote. Normally in range 0-255. A value < 0
 signifies an NEC repeat code.
 2. `addr` (`int`) Address from the remote.
 3. `ctrl` (`int`) The meaning of this is protocol dependent:  
 NEC: 0  
 Philips: this is toggled 1/0 on repeat button presses. If the button is held
 down it is not toggled. The  transmitter demo implements this behaviour.  
 Sony: 0 unless receiving a 20-bit stream, in which case it holds the extended
 value.
 4. Any args passed to the constructor.

Bound variable:  
 1. `verbose=False` If `True` emits debug output.

Method:
 1. `error_function` Arg: a function taking a single arg. If this is specified
 it will be called if an error occurs. The value corresponds to the error code
 (see below).

#### NEC classes

`NEC_8`, `NEC_16`

```python
from ir_rx.nec import NEC_8
```

Remotes using the NEC protocol can send 8 or 16 bit addresses. If the `NEC_16`
class receives an 8 bit address it will get a 16 bit value comprising the
address in bits 0-7 and its one's complement in bits 8-15.  
The `NEC_8` class enables error checking for remotes that return an 8 bit
address: the complement is checked and the address returned as an 8-bit value.
A 16-bit address will result in an error.

#### Sony classes

`SONY_12`, `SONY_15`, `SONY_20`

```python
from ir_rx.sony import SONY_15
```

The SIRC protocol comes in 3 variants: 12, 15 and 20 bits. `SONY_20` handles
bitstreams from all three types of remote. Choosing a class matching the remote
improves the timing reducing the likelihood of errors when handling repeats: in
20-bit mode SIRC timing when a button is held down is tight. A worst-case 20
bit block takes 39ms nominal, yet the repeat time is 45ms nominal.  
A single physical remote can issue more than one type of bitstream. The Sony
remote tested issued both 12 bit and 15 bit streams.

#### Philips classes

`RC5_IR`, `RC6_M0`

```python
from ir_rx.philips import RC5_IR
```

These support the RC-5 and RC-6 mode 0 protocols respectively.

# 4.1 Errors

IR reception is inevitably subject to errors, notably if the remote is operated
near the limit of its range, if it is not pointed at the receiver or if its
batteries are low. The user callback is not called when an error occurs.

On ESP8266 and ESP32 there is a further source of errors. This results from the
large and variable interrupt latency of the device which can exceed the pulse
duration. This causes pulses to be missed or their timing measured incorrectly.
On ESP8266 some improvment may be achieved by running the chip at 160MHz.

In general applications should provide user feedback of correct reception.
Users tend to press the key again if the expected action is absent.

In debugging a callback can be specified for reporting errors. The value passed
to the error function are represented by constants indicating the cause of the
error. These are as follows:

`BADSTART` A short (<= 4ms) start pulse was received. May occur due to IR
interference, e.g. from fluorescent lights. The TSOP4838 is prone to producing
200µs pulses on occasion, especially when using the ESP8266.  
`BADBLOCK` A normal data block: too few edges received. Occurs on the ESP8266
owing to high interrupt latency.  
`BADREP` A repeat block: an incorrect number of edges were received.  
`OVERRUN` A normal data block: too many edges received.  
`BADDATA` Data did not match check byte.  
`BADADDR` (`NEC_IR`) If `extended` is `False` the 8-bit address is checked
against the check byte. This code is returned on failure.  

# 4.2 Receiver platforms

Currently the ESP8266 suffers from [this issue](https://github.com/micropython/micropython/issues/5714).
Testing was therefore done without WiFi connectivity.

Philips protocols (especially RC-6) have tight timing constraints with short
pulses whose length must be determined with reasonable accuracy. The Sony 20
bit protocol also has a timing issue in that the worst case bit pattern takes
39ms nominal, yet the repeat time is 45ms nominal. These issues can lead to
errors particularly on slower targets. As discussed above, errors are to be
expected. It is up to the user to decide if the error rate is acceptable.

Reception was tested using Pyboard D SF2W, ESP8266 and ESP32 with signals from
remote controls (where available) and from the tranmitter in this repo. Issues
are listed below.

NEC: No issues.  
Sony 12 and 15 bit: No issues.  
Sony 20 bit: On ESP32 some errors occurred when repeats occurred.  
Philips RC-5: On ESP32 with one remote control many errors occurred, but paired
with the transmitter in this repo it worked.  
Philips RC-6: No issues. Only tested against the transmitter in this repo.

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
a Pyboard D SF2W at stock frequency. They were: NEC 1ms for normal data, 100μs
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
