# IR Receiver

##### [Main README](./README.md#1-ir-communication)

# 1. Hardware Requirements

The receiver is cross-platform. It requires an IR receiver chip to demodulate
the carrier. The chip must be selected for the frequency in use by the remote.
For 38KHz devices a receiver chip such as the Vishay TSOP4838 or the
[adafruit one](https://www.adafruit.com/products/157) is required. This
demodulates the 38KHz IR pulses and passes the demodulated pulse train to the
microcontroller. The tested chip returns a 0 level on carrier detect, but the
driver design ensures operation regardless of sense.

In my testing a 38KHz demodulator worked with 36KHz and 40KHz remotes, but this
is obviously neither guaranteed nor optimal.

The TSOP4838 can run from 3.3V or 5V supplies. The former should be used on
non-5V compliant hosts such as ESP32 and Raspberry Pi Pico and is fine on 5V
compliant hosts too.

The pin used to connect the decoder chip to the target is arbitrary. The test
program `acquire.py` uses the following pins by default:

| Host    | Pin | Notes |
|:-------:|:---:|:-----:|
| Pyboard | X3  |  |
| ESP32   | 23  |  |
| ESP8266 | 13  |  |
| D1 Mini | D7  | WeMos name for pin 13. |
| Pico    | 16  |  |

A remote using the NEC protocol is [this one](https://www.adafruit.com/products/389).

# 2. Installation and demo scripts

The receiver is a Python package. This minimises RAM usage: applications only
import the device driver for the protocol in use. It may be installed using
 [mpremote](https://docs.micropython.org/en/latest/reference/mpremote.html) on
 the PC:
```bash
$ mpremote mip install "github:peterhinch/micropython_ir/ir_rx"
```
There are no dependencies.

## 2.1 Test scripts

The demo can be used to characterise IR remotes where the protocol is known. It
displays the codes returned by each button. This can aid in the design of
receiver applications. The demo prints "running" every 5 seconds and reports
any data received from the remote.
```python
from ir_rx.test import test
```
Instructions will be displayed at the REPL.

If the protocol in use is unknown, there are two options: trial and error with
the above script or run the following:
```python
from ir_rx.acquire import test
test()
```
This script waits for a single burst from the remote and prints the timing of
the pulses followed by its best guess at the protocol. It correctly identifies
supported protocols, but can wrongly identify unsupported protocols. The
report produced by the script exposed to an unknown protocol is unpredictable.
The `test()` function returns a list of the mark and space periods (in μs).

# 3. The driver

This implements a class for each supported protocol. Each class is subclassed
from a common abstract base class in `__init__.py`.

Applications should instantiate the appropriate class with a callback. The
callback will run whenever an IR pulse train is received. Example running on a
Pyboard:
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

##### Constructor args:  
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

##### Methods:
 1. `error_function` Arg: a function taking a single `int` arg. If specified
 the function will be called if an error occurs. The arg value corresponds to
 the error code. Typical usage might be to provide some user feedback of
 incorrect reception although beware of occasional triggers by external events.
 In my testing the TSOP4838 produces 200µs pulses on occasion for no obvious
 reason. See [section 4](./RECEIVER.md#4-errors).
 2. `close` No args. Shuts down the pin and timer interrupts.

A function is provided to print errors in human readable form. This may be
invoked as follows:

```python
from ir_rx.print_error import print_error  # Optional print of error codes
# Assume ir is an instance of an IR receiver class
ir.error_function(print_error)
```
##### Class variables:
 1. `Timer_id=-1` By default the driver uses a software timer. The ESP32C3  does
 not support these. This class variable offers a workround, See
 [section 5.1](./RECEIVER.md#51-timer-id).
 2. There are constants defining the NEC repeat code and the error codes sent
 to the error function. They are discussed in [section 4](./RECEIVER.md#4-errors).

Users of `uasyncio` please see [Section 8](./RECEIVER.md#8-use-with-uasyncio).

#### NEC classes (includes Samsung)

`NEC_8`, `NEC_16`, `SAMSUNG`

Typical invocation:
```python
from ir_rx.nec import NEC_8
```

Remotes using the NEC protocol can send 8 or 16 bit addresses. If the `NEC_16`
class receives an 8 bit address it will get a 16 bit value comprising the
address in bits 0-7 and its one's complement in bits 8-15.  
The `NEC_8` class enables error checking for remotes that return an 8 bit
address: the complement is checked and the address returned as an 8-bit value.
A 16-bit address will result in an error.

The `SAMSUNG` class returns 16 bit address and data values. The remote sample
tested did not issue repeat codes - if a button is held down it simply repeated
the original value. In common with other NEC classes the callback receives a
value of 0 in the `ctrl` arg.

Thanks are due to J.E.Tannenbaum for information about the Samsung protocol.

#### Sony classes

`SONY_12`, `SONY_15`, `SONY_20`

Typical invocation:
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

Typical invocation:
```python
from ir_rx.philips import RC5_IR
```

These support the RC-5 (including RC-5X) and RC-6 mode 0 protocols
respectively.

#### Microsoft MCE class

`MCE`

Typical invocation:
```python
from ir_rx.mce import MCE
```

I have been unable to locate a definitive specification: the protocol was
analysed by a mixture of googling and experiment. Behaviour may change if I
acquire new information. The protocol is known as OrtekMCE and the remote
control is sold on eBay as VRC-1100.

The remote was designed for Microsoft Media Center and is used to control Kodi
on boxes such as the Raspberry Pi. With a suitable PC driver it can emulate a
PC keyboard and mouse. The mouse emulation uses a different protocol: the class
does not currently support it. Pressing mouse buttons and pad will cause the
error function (if provided) to be called.

Args passed to the callback comprise 4 bit `addr`, 6 bit `data` and 2 bit `ctrl`
with the latter having the value 0 for the first message and 2 for the message
sent on key release. Intermediate messages (where the key is held down) have
value 1.

There is a 4-bit checksum which is used by default. The algorithm requires an
initial 'seed' value which my testing proved to be 4. However the only
[documentation](http://www.hifi-remote.com/johnsfine/DecodeIR.html#OrtekMCE) I
could find stated that the value should be 3. I implemented this as a class
variable `MCE.init_cs=4`. This enables it to be changed if some remotes use 3.
If the value is set to -1 the check will be skipped.

# 4. Errors

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
error. These are driver ABC class variables and are as follows:

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

# 5. Receiver platforms

Currently the ESP8266 suffers from [this issue](https://github.com/micropython/micropython/issues/5714).
Testing was therefore done without WiFi connectivity. If the application uses
the WiFi regularly, or if an external process pings the board repeatedly, the
crash does not occur.

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

## 5.1 Timer ID

The ESP32C3 does not support software timers. This results in a crash. It is
possible to assign a hardware timer as follows (example is for NEC but applies
to any class):
```python
from ir_rx.nec import NEC_8
NEC_8.Timer_id = 0  # Use hardware timer 0
# Code omitted
ir = NEC_8(Pin(8, Pin.IN), callback)
```
Note that assigning a hardware timer is only possible on platforms where the
timer callback is a soft interrupt service routine (see below).

Thanks are due to @Pax-IT for diagnosing this problem.

# 6. Principle of operation

Protocol classes inherit from the abstract base class `IR_RX`. This uses a pin
interrupt to store in an array the time (in μs) of each transition of the pulse
train from the receiver chip. Arrival of the first edge starts a software timer
which runs for the expected duration of an IR block (`tblock`). The use of a
software timer ensures that `.decode` and the user callback can allocate.

When the timer times out its callback (`.decode`) decodes the data. `.decode`
is a method of the protocol specific subclass; on completion it calls the
`do_callback` method of the ABC. This resets the edge reception and calls
either the user callback or the error function (if provided).

The size of the array and the duration of the timer are protocol dependent and
are set by the subclasses. The `.decode` method is provided in the subclass.

CPU times used by `.decode` (not including the user callback) were measured on
a Pyboard D SF2W at stock frequency. They were: NEC 1ms for normal data, 100μs
for a repeat code. Philips codes: RC-5 900μs, RC-6 mode 0 5.5ms.

# 7. Unsupported protocols

It is possible to capture an IR burst from a remote and to re-create it using
the transmitter. This has limitations and is discussed in detail in
[the transmitter doc](./TRANSMITTER.md#5-unsupported-protocols).

# 8. Use with uasyncio

The receiver callback runs in a soft ISR (interrupt service routine) context.
In normal synchronous code this is unlikely to present problems, but the fact
that an interrupt can occur at any time means that care must be taken to avoid
a risk of disrupting `uasyncio` internal data. "Thread safe" techniques should
be used. In particular it is bad practice to create a task in the callback. A
simple approach is to use a [ThreadSafeQueue](https://github.com/peterhinch/micropython-async/blob/master/v3/docs/THREADING.md#22-threadsafequeue):

```python
import uasyncio as asyncio
from threadsafe import ThreadSafeQueue
from machine import Pin
from ir_rx import NEC_16

def callback(data, addr, ctrl, qu):  # Runs in ISR context
    if not qu.full():
        qu.put_sync((data, addr))

async def receiver(q):
    async for data in q:  # Task pauses here until data arrives
        print(f"Received {data}")

async def main():
    q = ThreadSafeQueue([0 for _ in range(20)])
    ir = NEC_16(Pin(16, Pin.IN), callback, q)
    await receiver(q)

asyncio.run(main())
```

The underlying issues are discussed [here](https://github.com/peterhinch/micropython-async/blob/master/v3/docs/INTERRUPTS.md)
and [here](https://github.com/peterhinch/micropython-async/blob/master/v3/docs/THREADING.md).

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

# Appendix 2 MCE Protocol

The bitstream comprises a header (2ms mark, 1ms space) followed by 16 bits of
Manchester encoded data with a bit time of 500μs. Data are encoded  
```
ccccddddddppaaaa
```
Where `aaaa` is the address, `pp` is the position (toggle) field, `dddddd` is
data and `cccc` is a checksum. This is calculated by counting the ones in
`ddddddppaaaa` and adding 4. Data are transmitted LSB first.

The only [doc](http://www.hifi-remote.com/johnsfine/DecodeIR.html#OrtekMCE) I
could find states that the checksum seed value is 3, but this did not match the
remote I have.
