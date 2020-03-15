# Device drivers for IR (infra red) remote controls

This repo provides a driver to receive from IR (infra red) remote controls and
a driver for IR "blaster" apps. The device drivers are nonblocking. They do not
require `uasyncio` but are compatible with it, and are designed for standard
firmware builds.

The receiver is cross platform and has been tested on Pyboard, ESP8266 and
ESP32.

#### [Receiver docs](./RECEIVER.md)

The transmitter driver is compatible with Pyboard (1.x and D series) and ESP32.
ESP8266 is unsupported; it seems incapable of generating the required signals.

#### [Transmitter docs](./TRANSMITTER.md)

# 1. IR communication

IR communication uses a carrier frequency to pulse the IR source. Modulation
takes the form of OOK (on-off keying). There are multiple protocols and at
least three options for carrier frequency: 36, 38 and 40KHz.

The drivers support NEC and Sony protocols plus two Philips protocols, namely
RC-5 and RC-6 mode 0. In the case of the transmitter the carrier frequency is a
runtime parameter: any value may be specified. The receiver uses a hardware
demodulator which should be purchased for the correct frequency. The receiver
device driver sees the demodulated signal and is hence carrier frequency
agnostic.

Examining waveforms from various remote controls it is evident that numerous
protocols exist. Some are doubtless proprietary and undocumented. The supported
protocols are those for which I managed to locate documentation. My preference
is for the NEC version. It has conservative timing and good provision for error
detection. RC-5 has limited error detection, and RC-6 mode 0 has rather fast
timing.

A remote using the NEC protocol is [this one](https://www.adafruit.com/products/389).

Remotes transmit an address and a data byte, plus in some cases an extra value.
The address denotes the physical device being controlled. The data defines the
button on the remote. Provision usually exists for differentiating between a
button repeatedly pressed and one which is held down; the mechanism is protocol
dependent.

# 2. Hardware Requirements

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

The transmitter requires a Pyboard 1.x (not Lite), a Pyboard D or an ESP32.
Output is via an IR LED which will need a transistor to provide sufficient
current. The ESP32 has significant limitations as a transmitter discussed
[here](./TRANSMITTER.md#52-esp32).
