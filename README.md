# Device drivers for IR (infra red) remote controls

This repo provides a driver to receive from IR (infra red) remote controls and
a driver for IR "blaster" apps. The device drivers are nonblocking. They do not
require `uasyncio` but are compatible with it, and are designed for standard
firmware builds.

The receiver is cross platform and has been tested on Pyboard, ESP8266, ESP32
and Raspberry Pi Pico.

In a typical use case the receiver is employed at the REPL to sniff the address
and data values associated with buttons on a remote control. The transmitter is
then used in an application to send those codes, emulating the remote control.

Other use cases involve running the receiver in an application. This enables an
IR remote to control a device such as a robot. This may be problematic on some
platforms. Please see [section 4](./README.md#4-receiver-limitations).

## Raspberry Pi Pico note

Early firmware has [this issue](https://github.com/micropython/micropython/issues/6866)
affecting USB communication with some PC's. This is now fixed. Please ensure
you are using up to date firmware.

#### [Receiver docs](./RECEIVER.md)

The transmitter driver is compatible with Pyboard (1.x and D series) and ESP32.
ESP8266 is unsupported; it seems incapable of generating the required signals.

#### [Transmitter docs](./TRANSMITTER.md)

# 1. IR communication

IR communication uses a carrier frequency to pulse the IR source. Modulation
takes the form of OOK (on-off keying). There are multiple protocols and at
least three options for carrier frequency: 36, 38 and 40KHz.

In the case of the transmitter the carrier frequency is a runtime parameter:
any value may be specified. The receiver uses a hardware demodulator which
should be purchased for the correct frequency. The receiver device driver sees
the demodulated signal and is hence carrier frequency agnostic.

Remotes transmit an address and a data byte, plus in some cases an extra value.
The address denotes the physical device being controlled. The data defines the
button on the remote. Provision usually exists for differentiating between a
button repeatedly pressed and one which is held down; the mechanism is protocol
dependent.

# 2. Supported protocols

The drivers support NEC and Sony protocols plus two Philips protocols, namely
RC-5 and RC-6 mode 0. There is also support for the OrtekMCE protocol used on
VRC-1100 remotes. These originally supported Microsoft Media Center but can be
used to control Kodi and (with a suitable receiver) to emulate a PC keyboard.
The Samsung protocol (NEC variant) is also supported.

Examining waveforms from various remote controls it is evident that numerous
protocols exist. Some are doubtless proprietary and undocumented. The supported
protocols are those for which I managed to locate documentation. My preference
is for the NEC version. It has conservative timing and good provision for error
detection. RC-5 has limited error detection, and RC-6 mode 0 has rather fast
timing.

A remote using the NEC protocol is [this one](https://www.adafruit.com/products/389).

# 3. Hardware Requirements

These are discussed in detail in the relevant docs; the following provides an
overview.

The receiver is cross-platform. It requires an IR receiver chip to demodulate
the carrier. The chip must be selected for the frequency in use by the remote.
For 38KHz devices a receiver chip such as the Vishay TSOP4838 or the
[adafruit one](https://www.adafruit.com/products/157) is required. This
demodulates the 38KHz IR pulses and passes the demodulated pulse train to the
microcontroller.

In my testing a 38KHz demodulator worked with 36KHz and 40KHz remotes, but this
is obviously neither guaranteed nor optimal.

The transmitter requires a Pyboard 1.x (not Lite), a Pyboard D, an ESP32 or
Raspberry Pico (RP2). Output is via an IR LED which will need a transistor to
provide sufficient current.

## 3.1 Carrier frequencies

These are as follows. The Panasonic remote appears to use a proprietary
protocol and is not supported by these drivers.

| Protocol  | F KHz | How found     | Support |
|:---------:|:-----:|:-------------:|:-------:|
| NEC       | 38    | Measured      | Y       |
| RC-5 RC-6 | 36    | Spec/measured | Y       |
| Sony      | 40    | Spec/measured | Y       |
| MCE       | 38    | Measured      | Y       | 
| Samsung   | 38    | Measured      | Y       |
| Panasonic | 36.3  | Measured      | N       |

# 4. Receiver limitations

The receiver uses a pin interrupt and depends on a quick response to a state
change on the pin. This is guaranteed on platforms which support hard IRQ's
such as the Pyboard and the RP4 Pico. The ESP32 and ESP8266 only support soft
IRQ's. This means that, if code such as WiFi communication is running
concurrently, reliable reception may be problematic.

# 5. References

Sources of information about IR protocols. The `sbprojects.net` site is an
excellent resource.  
[General information about IR](https://www.sbprojects.net/knowledge/ir/)

Also [IRMP](https://www.mikrocontroller.net/articles/IRMP_-_english)

The NEC protocol:  
[altium](http://techdocs.altium.com/display/FPGA/NEC+Infrared+Transmission+Protocol)  
[circuitvalley](http://www.circuitvalley.com/2013/09/nec-protocol-ir-infrared-remote-control.html)  
[sbprojects.net](https://www.sbprojects.net/knowledge/ir/nec.php)

The Samsung protocol:  
[Rustic Engineering](https://rusticengineering.wordpress.com/2011/02/09/infrared-room-control-with-samsung-ir-protocol/)  
[TechDesign Electronics](https://www.techdesign.be/projects/011/011_waves.htm) Waveforms of various protocols.  


Philips protocols:  
[RC5 Wikipedia](https://en.wikipedia.org/wiki/RC-5)  
[RC5 sbprojects.net](https://www.sbprojects.net/knowledge/ir/rc5.php)  
[RC6 sbprojects.net](https://www.sbprojects.net/knowledge/ir/rc6.php)

Sony protocol:  
[SIRC sbprojects.net](https://www.sbprojects.net/knowledge/ir/sirc.php)

MCE protocol:  
[OrtekMCE](http://www.hifi-remote.com/johnsfine/DecodeIR.html#OrtekMCE)

IR decoders (C sourcecode):  
[in the Linux kernel](https://github.com/torvalds/linux/tree/master/drivers/media/rc)

Interesting summary of IR protools (with thanks to Martin Bless):  
[IRMP](https://www.mikrocontroller.net/articles/IRMP_-_english#IR_Protocols)
