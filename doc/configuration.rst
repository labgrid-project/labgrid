Configuration
=============
This chapter describes the individual drivers and resources used in a device
configuration.
Drivers can depend on resources or other drivers, whereas resources
have no dependencies.

.. image:: res/config_graph.svg
   :width: 50%

Here the resource `RawSerialPort`_ provides the information for the
`SerialDriver`_, which in turn is needed by the `ShellDriver`_.
Driver dependency resolution is done by searching for the driver which
implements the dependent protocol, all drivers implement one or more protocols.

Resources
---------

Serial Ports
~~~~~~~~~~~~

RawSerialPort
+++++++++++++
A :any:`RawSerialPort` is a serial port which is identified via the device path
on the local computer.
Take note that re-plugging USB serial converters can result in a different
enumeration order.

.. code-block:: yaml

   RawSerialPort:
     port: '/dev/ttyUSB0'
     speed: 115200

The example would access the serial port ``/dev/ttyUSB0`` on the local computer
with a baud rate of ``115200``.

Arguments:
  - port (str): path to the serial device
  - speed (int, default=115200): desired baud rate

Used by:
  - `SerialDriver`_

NetworkSerialPort
+++++++++++++++++
A :any:`NetworkSerialPort` describes a serial port which is exported over the
network, usually using `RFC2217 <https://datatracker.ietf.org/doc/rfc2217/>`_
or raw TCP.

.. code-block:: yaml

   NetworkSerialPort:
     host: 'remote.example.computer'
     port: 53867
     speed: 115200

The example would access the serial port on computer
``remote.example.computer`` via port ``53867`` and use a baud rate of
``115200`` with the RFC2217 protocol.

Arguments:
  - host (str): hostname of the remote host
  - port (str): TCP port on the remote host to connect to
  - speed (int, default=115200): baud rate of the serial port
  - protocol (str, default="rfc2217"): protocol used for connection: raw or
    rfc2217

Used by:
  - `SerialDriver`_

ModbusRTU
+++++++++
A :any:`ModbusRTU` resource is required to use the `ModbusRTUDriver`_.
`Modbus RTU <https://en.wikipedia.org/wiki/Modbus>`_ is a communication
protocol used to control many different kinds of electronic systems, such as
thermostats, power plants, etc.
Modbus is normally implemented on top of RS-485, though this is not strictly
necessary, as long as the Modbus network only has one master (and up to 256
slaves).

This resource only supports local usage and will not work with an exporter.

.. code-block:: yaml

    ModbusRTU:
      port: '/dev/ttyUSB0'
      address: 16
      speed: 115200
      timeout: 0.25

Arguments:
  - port (str): tty the instrument is connected to, e.g. ``/dev/ttyUSB0``
  - address (int): slave address on the modbus, e.g. 16
  - speed (int, default=115200): baud rate of the serial port
  - timeout (float, default=0.25): timeout in seconds

Used by:
  - `ModbusRTUDriver`_

USBSerialPort
+++++++++++++
A :any:`USBSerialPort` describes a serial port which is connected via USB and
is identified by matching udev properties.
This allows identification through hot-plugging or rebooting.

.. code-block:: yaml

   USBSerialPort:
     match:
       ID_SERIAL_SHORT: 'P-00-00682'
       ID_USB_INTERFACE_NUM: '00'
     speed: 115200

The example would search for a USB serial converter with a given serial number
(``ID_SERIAL_SHORT`` = ``P-00-00682``) and use first interface
(``ID_USB_INTERFACE_NUM`` = ``00``) with a baud rate of 115200.

The ``ID_SERIAL_SHORT`` and ``ID_USB_INTERFACE_NUM`` properties are set by the
``usb_id`` builtin helper program.

Arguments:
  - match (dict): key and value pairs for a udev match, see `udev Matching`_
  - speed (int, default=115200): baud rate of the serial port

Used by:
  - `SerialDriver`_

Power Ports
~~~~~~~~~~~

NetworkPowerPort
++++++++++++++++
A :any:`NetworkPowerPort` describes a remotely switchable power port.

.. code-block:: yaml

   NetworkPowerPort:
     model: 'gude'
     host: 'powerswitch.example.computer'
     index: 0

The example describes port 0 on the remote power switch
``powerswitch.example.computer``, which is a ``gude`` model.

Arguments:
  - model (str): model of the power switch
  - host (str): hostname of the power switch
  - index (int): number of the port to switch

The ``model`` property selects one of several `backend implementations
<https://github.com/labgrid-project/labgrid/tree/master/labgrid/driver/power>`_.
Currently available are:

``apc``
  Controls *APU PDUs* via SNMP.

``digipower``
  Controls *DigiPower PDUs* via a simple HTTP API.

``digitalloggers_http``
  Controls *Digital Loggers PDUs* that use the legacy HTTP API. Note that
  host argument must include the protocol, such as
  ``http://192.168.0.3`` or ``http://admin:pass@192.168.0.4``.

``digitalloggers_restapi``
  Controls *Digital Loggers PDUs* that use the REST API. Note that
  host argument must include the protocol, such as
  ``http://192.168.0.3`` or ``https://admin:pass@192.168.0.4``.
  By default, only authenticated users may access the REST API.
  HTTPS queries intentially ignore ssl certificate validation, since
  the as-shipped certificate is self-signed.

``eaton``
  Controls *Eaton ePDUs* via SNMP.

``eg_pms2_network``
  Controls *EG_PMS2_LAN* and *EG_PMS2_WLAN* devices, through simple HTTP POST
  and GET requests. The device requires a password for logging into the
  control interface, this module deliberately uses the standard password ``1``
  and is not compatible with a different password.

``eth008``
  Controls *Robot-Electronics eth008* via a simple HTTP API.

``gude``
  Controls *Gude PDUs* via a simple HTTP API.

``gude24``
  Controls *Gude Expert Power Control 8008 PDUs* via a simple HTTP API.

``gude8031``
  Controls *Gude Expert Power Control 8031 PDUs* and *Gude Expert Power Control 87-1210-18 PDUs* via a simple HTTP API.

``gude8225``
  Controls *Gude Expert Power Control 8225 PDUs* via a simple HTTP API.

``gude8316``
  Controls *Gude Expert Power Control 8316 PDUs* via a simple HTTP API.

``mfi_mpower``
  Controls the *Ubiquity mFi mPower* Power Strip with Ethernet and Wi-Fi connectivity via HTTP.
  Tested on a mFi mPower Pro EU device.

``netio``
  Controls *NETIO 4-Port PDUs* via a simple HTTP API.

``netio_kshell``
  Controls *NETIO 4C PDUs* via a Telnet interface.

``raritan``
  Controls *Raritan PDUs* via SNMP.

``rest``
  This is a generic backend for PDU implementations which can be controlled via
  HTTP PUT and GET requests.
  See the `docstring in the module
  <https://github.com/labgrid-project/labgrid/blob/master/labgrid/driver/power/rest.py>`__
  for details.

``sentry``
  Controls *Sentry PDUs* via SNMP using Sentry3-MIB.
  It was tested on *CW-24VDD* and *4805-XLS-16*.

``shelly_gen1``
  Controls relays of *Shelly* devices using the Gen 1 Device API.
  See the `docstring in the module
  <https://github.com/labgrid-project/labgrid/blob/master/labgrid/driver/power/shelly_gen1.py>`__
  for details.

``siglent``
  Controls *Siglent SPD3000X* series modules via the `vxi11 Python module
  <https://pypi.org/project/python-vxi11/>`_.

``simplerest``
  This is a generic backend for PDU implementations which can be controlled via
  HTTP GET requests (both set and get).
  See the `docstring in the module
  <https://github.com/labgrid-project/labgrid/blob/master/labgrid/driver/power/simplerest.py>`__
  for details.

``tplink``
  Controls *TP-Link power strips* via `python-kasa
  <https://github.com/python-kasa/python-kasa>`_.

``tinycontrol``
  Controls a tinycontrol.eu IP Power Socket via HTTP.
  It was tested on the *6G10A v2* model.
  `Manual <https://tinycontrol.pl/media/documents/manual_IP_Power_Socket__6G10A_v2_LANLIS-010-015_En-1.pdf>`__

``poe_mib``
  Controls PoE switches using the PoE SNMP administration MiBs.

``ubus``
  Controls *PoE switches* running OpenWrt using the *ubus* interface.
  Further information available at <https://openwrt.org/docs/techref/ubus>

Used by:
  - `NetworkPowerDriver`_

PDUDaemonPort
+++++++++++++
A :any:`PDUDaemonPort` describes a PDU port accessible via `PDUDaemon
<https://github.com/pdudaemon/pdudaemon>`_.
As one PDUDaemon instance can control many PDUs, the instance name from the
PDUDaemon configuration file needs to be specified.

.. code-block:: yaml

   PDUDaemonPort:
     host: 'pduserver'
     pdu: 'apc-snmpv3-noauth'
     index: 1

The example describes port ``1`` on the PDU configured as
``apc-snmpv3-noauth``, with PDUDaemon running on the host ``pduserver``.

Arguments:
  - host (str): name of the host running the PDUDaemon
  - pdu (str): name of the PDU in the configuration file
  - index (int): index of the power port on the PDU

Used by:
  - `PDUDaemonDriver`_

YKUSHPowerPort
++++++++++++++
A :any:`YKUSHPowerPort` describes a *YEPKIT YKUSH* USB (HID) switchable USB
hub.

.. code-block:: yaml

   YKUSHPowerPort:
     serial: 'YK12345'
     index: 1

The example describes port 1 on the YKUSH USB hub with the
serial ``YK12345``.
Use ``ykushcmd -l`` to get your serial number.

Arguments:
  - serial (str): serial number of the YKUSH hub
  - index (int): number of the port to switch

Used by:
  - `YKUSHPowerDriver`_

NetworkYKUSHPowerPort
+++++++++++++++++++++
A :any:`NetworkYKUSHPowerPort` describes a `YKUSHPowerPort`_ available on a
remote computer.

USBPowerPort
++++++++++++
A :any:`USBPowerPort` describes a generic switchable USB hub as supported by
`uhubctl <https://github.com/mvp/uhubctl>`_.

.. code-block:: yaml

   USBPowerPort:
     match:
       ID_PATH: 'pci-0000:00:14.0-usb-0:2:1.0'
     index: 1

The example describes port 1 on the hub with the ID_PATH
``pci-0000:00:14.0-usb-0:2:1.0``.
(use ``udevadm info /sys/bus/usb/devices/...`` to find the ID_PATH value)

Arguments:
  - index (int): number of the port to switch
  - match (dict): key and value pairs for a udev match, see `udev Matching`_

Used by:
  - `USBPowerDriver`_

.. note::
   labgrid requires that the interface is contained in the ID_PATH.
   This usually means that the ID_PATH should end with ``:1.0``.
   Only this first interface is registered with the ``hub`` driver labgrid is
   looking for, paths without the interface will fail to match since they use
   the ``usb`` driver.

SiSPMPowerPort
++++++++++++++
A :any:`SiSPMPowerPort` describes a *GEMBIRD SiS-PM* as supported by
`sispmctl <https://sourceforge.net/projects/sispmctl/>`_.

.. code-block:: yaml

   SiSPMPowerPort:
     match:
       ID_PATH: 'platform-1c1a400.usb-usb-0:2'
     index: 1

The example describes port 1 on the hub with the ID_PATH
``platform-1c1a400.usb-usb-0:2``.

Arguments:
  - index (int): number of the port to switch
  - match (dict): key and value pairs for a udev match, see `udev Matching`_

Used by:
  - `SiSPMPowerDriver`_

TasmotaPowerPort
++++++++++++++++
A :any:`TasmotaPowerPort` resource describes a switchable `Tasmota
<https://tasmota.github.io/docs/>`_ power outlet accessed over *MQTT*.

.. code-block:: yaml

   TasmotaPowerPort:
     host: 'this.is.an.example.host.com'
     status_topic: 'stat/tasmota_575A2B/POWER'
     power_topic: 'cmnd/tasmota_575A2B/POWER'
     avail_topic: 'tele/tasmota_575A2B/LWT'

The example uses a *Mosquitto* server at ``this.is.an.example.host.com`` and
has the topics setup for a Tasmota power port that has the ID ``575A2B``.

Arguments:
  - host (str): hostname of the MQTT server
  - status_topic (str): topic that signals the current status as "ON" or "OFF"
  - power_topic (str): topic that allows switching the status between "ON" and
    "OFF"
  - avail_topic (str): topic that signals the availability of the Tasmota power
    outlet

Used by:
  - `TasmotaPowerDriver`_

Digital Outputs
~~~~~~~~~~~~~~~

ModbusTCPCoil
+++++++++++++
A :any:`ModbusTCPCoil` describes a coil accessible via *Modbus TCP*.

.. code-block:: yaml

   ModbusTCPCoil:
     host: '192.168.23.42'
     coil: 1

The example describes the coil with the address ``1`` on the Modbus TCP device
``192.168.23.42``.

Arguments:
  - host (str): hostname of the Modbus TCP server e.g. ``192.168.23.42:502``
  - coil (int): index of the coil, e.g. ``3``
  - invert (bool, default=False): whether the logic level is inverted
    (active-low)
  - write_multiple_coils (bool, default=False): whether to perform write
    using "write multiple coils" method instead of "write single coil"

Used by:
  - `ModbusCoilDriver`_

DeditecRelais8
++++++++++++++
A :any:`DeditecRelais8` describes a *Deditec USB GPO module* with 8 relays.

.. code-block:: yaml

   DeditecRelais8:
     index: 1
     invert: false
     match:
       ID_PATH: 'pci-0000:00:14.0-usb-0:2:1.0'

Arguments:
  - index (int): number of the relay to use
  - invert (bool, default=False): whether the logic level is inverted
    (active-low)
  - match (dict): key and value pairs for a udev match, see `udev Matching`_

Used by:
  - `DeditecRelaisDriver`_

OneWirePIO
++++++++++
A :any:`OneWirePIO` describes a *1-Wire* programmable I/O pin.

.. code-block:: yaml

   OneWirePIO:
     host: 'example.computer'
     path: '/29.7D6913000000/PIO.0'
     invert: false

The example describes a ``PIO.0`` at device address ``29.7D6913000000`` via the
1-Wire server on ``example.computer``.

Arguments:
  - host (str): hostname of the remote system running the 1-Wire server
  - path (str): path on the server to the programmable I/O pin
  - invert (bool, default=False): whether the logic level is inverted
    (active-low)

Used by:
  - `OneWirePIODriver`_

LXAIOBusPIO
+++++++++++
An :any:`LXAIOBusPIO` resource describes a single PIO pin on an LXAIOBusNode.

.. code-block:: yaml

   LXAIOBusPIO:
     host: 'localhost:8080'
     node: 'IOMux-00000003'
     pin: 'OUT0'
     invert: false

The example uses an lxa-iobus-server running on ``localhost:8080``, with node
``IOMux-00000003`` and pin ``OUT0``.

Arguments:
  - host (str): hostname with port of the lxa-io-bus server
  - node (str): name of the node to use
  - pin (str): name of the pin to use
  - invert (bool, default=False): whether to invert the pin

Used by:
  - `LXAIOBusPIODriver`_

NetworkLXAIOBusPIO
++++++++++++++++++
A :any:`NetworkLXAIOBusPIO` describes an `LXAIOBusPIO`_ exported over the network.

HIDRelay
++++++++
An :any:`HIDRelay` resource describes a single output of an HID protocol based
USB relays.
It currently supports the widely used *dcttech USBRelay* and *lctech LCUS*

.. code-block:: yaml

   HIDRelay:
     index: 2
     invert: false
     match:
       ID_PATH: 'pci-0000:00:14.0-usb-0:2:1.0'

Arguments:
  - index (int, default=1): number of the relay to use
  - invert (bool, default=False): whether to invert the relay
  - match (dict): key and value pairs for a udev match, see `udev Matching`_

Used by:
  - `HIDRelayDriver`_

HttpDigitalOutput
+++++++++++++++++
An :any:`HttpDigitalOutput` resource describes a generic digital output that
can be controlled via HTTP.

.. code-block:: yaml

   HttpDigitalOutput:
     url: 'http://host.example/some/endpoint'
     body_asserted: 'On'
     body_deasserted: 'Off'

The example assumes a simple scenario where the same URL is used for PUT
requests that set the output state and GET requests to get the current state.
It also assumes that the returned state matches either "On" or "Off" exactly.

The `HttpDigitalOutputDriver`_ also supports more advanced use cases where the
current state is fetched from another URL and is interpreted using regular
expressions.

Arguments:
  - url (str): URL to use for setting a new state
  - body_asserted (str): request body to send to assert the output
  - body_deasserted (str): request body to send to de-assert the output
  - method (str, default="PUT"): HTTP method to set a new state

  - url_get (str): optional, URL to use instead of ``url`` for getting the state
  - body_get_asserted (str): optional, regular expression that matches an asserted response body
  - body_get_deasserted (str): optional, regular expression that matches a de-asserted response body

Used by:
  - `HttpDigitalOutputDriver`_

NetworkHIDRelay
+++++++++++++++
A :any:`NetworkHIDRelay` describes an `HIDRelay`_ exported over the network.

SysfsGPIO
+++++++++

A :any:`SysfsGPIO` resource describes a GPIO line.

.. code-block:: yaml

   SysfsGPIO:
     index: 12

Arguments:
  - index (int): index of the GPIO line

Used by:
  - `GpioDigitalOutputDriver`_

MatchedSysfsGPIO
++++++++++++++++
A :any:`MatchedSysfsGPIO` describes a GPIO line, like a `SysfsGPIO`_.
The gpiochip is identified by matching udev properties. This allows
identification through hot-plugging or rebooting for controllers like
USB based gpiochips.

.. code-block:: yaml

   MatchedSysfsGPIO:
     match:
       '@SUBSYSTEM': 'usb'
       '@ID_SERIAL_SHORT': 'D38EJ8LF'
     pin: 0

The example would search for a USB gpiochip with the key `ID_SERIAL_SHORT`
and the value `D38EJ8LF` and use the pin 0 of this device.
The `ID_SERIAL_SHORT` property is set by the usb_id builtin helper program.

Arguments:
  - match (dict): key and value pairs for a udev match, see `udev Matching`_
  - pin (int): gpio pin number within the matched gpiochip.

Used by:
  - `GpioDigitalOutputDriver`_

NetworkService
~~~~~~~~~~~~~~
A :any:`NetworkService` describes a remote SSH connection.

.. code-block:: yaml

   NetworkService:
     address: 'example.computer'
     username: 'root'

The example describes a remote SSH connection to the computer
``example.computer`` with the username ``root``.
Set the optional password password property to make SSH login with a password
instead of the key file.

When used with ``labgrid-exporter``, the address can contain a device scope
suffix (such as ``%eth1``), which is especially useful with overlapping address
ranges or link-local IPv6 addresses.
In that case, the SSH connection will be proxied via the exporter, using
``socat`` and the ``labgrid-bound-connect`` sudo helper.
These and the sudo configuration needs to be prepared by the administrator.

Arguments:
  - address (str): hostname of the remote system
  - username (str): username used by SSH
  - password (str, default=""): password used by SSH
  - port (int, default=22): port used by SSH

Used by:
  - `SSHDriver`_

USBMassStorage
~~~~~~~~~~~~~~
A :any:`USBMassStorage` resource describes a USB memory stick or similar
device.

.. code-block:: yaml

   USBMassStorage:
     match:
       ID_PATH: 'pci-0000:06:00.0-usb-0:1.3.2:1.0-scsi-0:0:0:3'

Writing images to disk requires installation of ``dd`` or optionally
``bmaptool`` on the same system as the block device.

For mounting the file system and writing into it,
`PyGObject <https://pygobject.readthedocs.io/>`_ must be installed.
For Debian, the necessary packages are `python3-gi` and `gir1.2-udisks-2.0`.
This is not required for writing images to disks.

Arguments:
  - match (dict): key and value pairs for a udev match, see `udev Matching`_

Used by:
  - `USBStorageDriver`_

NetworkUSBMassStorage
~~~~~~~~~~~~~~~~~~~~~
A :any:`NetworkUSBMassStorage` resource describes a USB memory stick or similar
device available on a remote computer.

The NetworkUSBMassStorage can be used in test cases by calling the
``write_files()``, ``write_image()``, and ``get_size()`` functions.

SigrokDevice
~~~~~~~~~~~~
A :any:`SigrokDevice` resource describes a *Sigrok* device. To select a
specific device from all connected supported devices use the
`SigrokUSBDevice`_.

.. code-block:: yaml

   SigrokDevice:
     driver: 'fx2lafw'
     channels: 'D0=CLK,D1=DATA'

Arguments:
  - driver (str): name of the sigrok driver to use
  - channels (str): optional, channel mapping as described in the
    ``sigrok-cli`` man page
  - channel_group (str): optional, channel group as described in the
    ``sigrok-cli`` man page

Used by:
  - `SigrokDriver`_

IMXUSBLoader
~~~~~~~~~~~~
An :any:`IMXUSBLoader` resource describes a USB device in the imx loader state.

.. code-block:: yaml

   IMXUSBLoader:
     match:
       ID_PATH: 'pci-0000:06:00.0-usb-0:1.3.2:1.0'

Arguments:
  - match (dict): key and value pairs for a udev match, see `udev Matching`_

Used by:
  - `IMXUSBDriver`_
  - `UUUDriver`_
  - `BDIMXUSBDriver`_

MXSUSBLoader
~~~~~~~~~~~~
An :any:`MXSUSBLoader` resource describes a USB device in the *MXS loader
state*.

.. code-block:: yaml

   MXSUSBLoader:
     match:
       ID_PATH: 'pci-0000:06:00.0-usb-0:1.3.2:1.0'

Arguments:
  - match (dict): key and value pairs for a udev match, see `udev Matching`_

Used by:
  - `MXSUSBDriver`_
  - `IMXUSBDriver`_
  - `UUUDriver`_

RKUSBLoader
~~~~~~~~~~~
An :any:`RKUSBLoader` resource describes a USB device in the *Rockchip loader
state*.

.. code-block:: yaml

   RKUSBLoader:
     match:
       ID_PATH: 'pci-0000:06:00.0-usb-0:1.3.2:1.0'

Arguments:
  - match (dict): key and value pairs for a udev match, see `udev Matching`_

Used by:
  - `RKUSBDriver`_

NetworkMXSUSBLoader
~~~~~~~~~~~~~~~~~~~
A :any:`NetworkMXSUSBLoader` describes an `MXSUSBLoader`_ available on a remote
computer.

NetworkIMXUSBLoader
~~~~~~~~~~~~~~~~~~~
A :any:`NetworkIMXUSBLoader` describes an `IMXUSBLoader`_ available on a remote
computer.

NetworkRKUSBLoader
~~~~~~~~~~~~~~~~~~
A :any:`NetworkRKUSBLoader` describes an `RKUSBLoader`_ available on a remote
computer.

AndroidUSBFastboot
~~~~~~~~~~~~~~~~~~
An :any:`AndroidUSBFastboot` resource describes a USB device in the *Fastboot
state*.
Previously, this resource was named AndroidFastboot and this name still
supported for backwards compatibility.

.. code-block:: yaml

   AndroidUSBFastboot:
     match:
       ID_PATH: 'pci-0000:06:00.0-usb-0:1.3.2:1.0'

Arguments:
  - usb_vendor_id (str, default="1d6b"): USB vendor ID to be compared with the
    ``ID_VENDOR_ID`` udev property
  - usb_product_id (str, default="0104"): USB product ID, to be compared with
    the ``ID_MODEL_ID`` udev property
  - match (dict): key and value pairs for a udev match, see `udev Matching`_

Used by:
  - `AndroidFastbootDriver`_

AndroidNetFastboot
~~~~~~~~~~~~~~~~~~
An :any:`AndroidNetFastboot` resource describes a network device in *Fastboot
state*.

.. code-block:: yaml

   AndroidNetFastboot:
     address: '192.168.23.42'

Arguments:
  - address (str): ip address of the fastboot device
  - port (int, default=5554): udp/tcp fastboot port that is used in the
    device. (e.g. Barebox uses port 5554)
  - protocol (str, default="udp"): which protocol should be used when issuing
    fastboot commands. (Barebox supports currently only the udp protocol)

Used by:
  - `AndroidFastbootDriver`_

DFUDevice
~~~~~~~~~
A :any:`DFUDevice` resource describes a USB device in DFU (Device Firmware
Upgrade) mode.

.. code-block:: yaml

   DFUDevice:
     match:
       ID_PATH: 'pci-0000:06:00.0-usb-0:1.3.2:1.0'

Arguments:
  - match (dict): key and value pairs for a udev match, see `udev Matching`_

Used by:
  - `DFUDriver`_

NetworkInterface
~~~~~~~~~~~~~~~~
A :any:`NetworkInterface` resource describes a network adapter (such as
Ethernet or WiFi)

.. code-block:: yaml

   NetworkInterface:
     ifname: 'eth0'

Arguments:
  - ifname (str): name of the interface

Used by:
  - `NetworkInterfaceDriver`_
  - `RawNetworkInterfaceDriver`_

USBNetworkInterface
~~~~~~~~~~~~~~~~~~~
A :any:`USBNetworkInterface` resource describes a USB network adapter (such as
Ethernet or WiFi)

.. code-block:: yaml

   USBNetworkInterface:
     match:
       ID_PATH: 'pci-0000:06:00.0-usb-0:1.3.2:1.0'

Arguments:
  - match (dict): key and value pairs for a udev match, see `udev Matching`_

Used by:
  - `NetworkInterfaceDriver`_
  - `RawNetworkInterfaceDriver`_

RemoteNetworkInterface
~~~~~~~~~~~~~~~~~~~~~~
A :any:`RemoteNetworkInterface` resource describes a `NetworkInterface`_ or
`USBNetworkInterface`_ resource available on a remote computer.

AlteraUSBBlaster
~~~~~~~~~~~~~~~~
An :any:`AlteraUSBBlaster` resource describes an Altera USB blaster.

.. code-block:: yaml

   AlteraUSBBlaster:
     match:
       ID_PATH: 'pci-0000:06:00.0-usb-0:1.3.2:1.0'

Arguments:
  - match (dict): key and value pairs for a udev match, see `udev Matching`_

Used by:
  - `OpenOCDDriver`_
  - `QuartusHPSDriver`_

USBDebugger
~~~~~~~~~~~
A :any:`USBDebugger` resource describes a JTAG USB adapter (for example an
*FTDI FT2232H*).

.. code-block:: yaml

   USBDebugger:
     match:
       ID_PATH: 'pci-0000:00:10.0-usb-0:1.4'

Arguments:
  - match (dict): key and value pairs for a udev match, see `udev Matching`_

Used by:
  - `OpenOCDDriver`_

SNMPEthernetPort
~~~~~~~~~~~~~~~~
A :any:`SNMPEthernetPort` resource describes a port on an Ethernet switch,
which is accessible via SNMP.

.. code-block:: yaml

   SNMPEthernetPort:
     switch: 'switch-012'
     interface: '17'

Arguments:
  - switch (str): host name of the Ethernet switch
  - interface (str): interface name

Used by:
  - None

SigrokUSBDevice
~~~~~~~~~~~~~~~
A :any:`SigrokUSBDevice` resource describes a *Sigrok* USB device.

.. code-block:: yaml

   SigrokUSBDevice:
     driver: 'fx2lafw'
     channels: 'D0=CLK,D1=DATA'
     match:
       ID_PATH: 'pci-0000:06:00.0-usb-0:1.3.2:1.0'

Arguments:
  - driver (str): name of the sigrok driver to use
  - channels (str): optional, channel mapping as described in the
    ``sigrok-cli`` man page
  - channel_group (str): optional, channel group as described in the
    ``sigrok-cli`` man page
  - match (dict): key and value pairs for a udev match, see `udev Matching`_

Used by:
  - `SigrokDriver`_

NetworkSigrokUSBDevice
~~~~~~~~~~~~~~~~~~~~~~
A :any:`NetworkSigrokUSBDevice` resource describes a *Sigrok* USB device
connected to a host which is exported over the network.
The `SigrokDriver`_ will access it via SSH.

SigrokUSBSerialDevice
~~~~~~~~~~~~~~~~~~~~~
A :any:`SigrokUSBSerialDevice` resource describes a *Sigrok* device which
communicates over a USB serial port instead of being a USB device itself (see
`SigrokUSBDevice`_ for that case).

.. code-block:: yaml

   SigrokUSBSerialDevice:
     driver: 'manson-hcs-3xxx'
     match:
       '@ID_SERIAL_SHORT': 'P-00-02389'

Arguments:
  - driver (str): name of the sigrok driver to use
  - channels (str): optional, channel mapping as described in the
    ``sigrok-cli`` man page
  - channel_group (str): optional, channel group as described in the
    ``sigrok-cli`` man page
  - match (dict): key and value pairs for a udev match, see `udev Matching`_

Used by:
  - `SigrokPowerDriver`_
  - `SigrokDmmDriver`_

USBSDMuxDevice
~~~~~~~~~~~~~~
A :any:`USBSDMuxDevice` resource describes a Pengutronix
`USB-SD-Mux <https://www.pengutronix.de/de/2017-10-23-usb-sd-mux-automated-sd-card-juggler.html>`_
device.

.. code-block:: yaml

   USBSDMuxDevice:
     match:
       '@ID_PATH': 'pci-0000:00:14.0-usb-0:1.2'

Arguments:
  - match (dict): key and value pairs for a udev match, see `udev Matching`_

Used by:
  - `USBSDMuxDriver`_
  - `USBStorageDriver`_

NetworkUSBSDMuxDevice
~~~~~~~~~~~~~~~~~~~~~
A :any:`NetworkUSBSDMuxDevice` resource describes a `USBSDMuxDevice`_ available
on a remote computer.

LXAUSBMux
~~~~~~~~~
An :any:`LXAUSBMux` resource describes a *Linux Automation GmbH USB-Mux* device.

.. code-block:: yaml

   LXAUSBMux:
     match:
       '@ID_PATH': 'pci-0000:00:14.0-usb-0:1.2'

Arguments:
  - match (dict): key and value pairs for a udev match, see `udev Matching`_

Used by:
  - `LXAUSBMuxDriver`_

NetworkLXAUSBMux
~~~~~~~~~~~~~~~~
A :any:`NetworkLXAUSBMux` resource describes an `LXAUSBMux`_ available on a
remote computer.

USBSDWireDevice
~~~~~~~~~~~~~~~
A :any:`USBSDWireDevice` resource describes a Tizen
`SD Wire device <https://web.archive.org/web/20240121081917/https://wiki.tizen.org/SDWire>`_.

.. code-block:: yaml

   USBSDWireDevice:
     match:
       '@ID_PATH': 'pci-0000:00:14.0-usb-0:1.2'

Arguments:
  - match (dict): key and value pairs for a udev match, see `udev Matching`_

Used by:
  - `USBSDWireDriver`_
  - `USBStorageDriver`_

NetworkUSBSDWireDevice
~~~~~~~~~~~~~~~~~~~~~~
A :any:`NetworkUSBSDWireDevice` resource describes a `USBSDWireDevice`_ available
on a remote computer.

USBVideo
~~~~~~~~
A :any:`USBVideo` resource describes a USB video camera which is supported by a
Video4Linux2 (v4l2) kernel driver.

.. code-block:: yaml

   USBVideo:
     match:
       '@ID_PATH': 'pci-0000:00:14.0-usb-0:1.2'

Arguments:
  - match (dict): key and value pairs for a udev match, see `udev Matching`_

Used by:
  - `USBVideoDriver`_

NetworkUSBVideo
~~~~~~~~~~~~~~~
A :any:`NetworkUSBVideo` resource describes a `USBVideo`_ resource available
on a remote computer.

USBAudioInput
~~~~~~~~~~~~~
A :any:`USBAudioInput` resource describes a USB audio input which is supported
by an ALSA kernel driver.

.. code-block:: yaml

   USBAudioInput:
     match:
       ID_PATH: 'pci-0000:00:14.0-usb-0:3:1.0'

Arguments:
  - index (int, default=0): ALSA PCM device number (as in
    ``hw:CARD=<card>,DEV=<index>``)
  - match (dict): key and value pairs for a udev match, see `udev Matching`_

Used by:
  - `USBAudioInputDriver`_

NetworkUSBAudioInput
~~~~~~~~~~~~~~~~~~~~
A :any:`NetworkUSBAudioInput` resource describes a `USBAudioInput`_ resource
available on a remote computer.

USBTMC
~~~~~~
A :any:`USBTMC` resource describes an oscilloscope connected via the *USB TMC
protocol*.
The low-level communication is handled by the "usbtmc" kernel driver.

.. code-block:: yaml

   USBTMC:
     match:
       '@ID_PATH': 'pci-0000:00:14.0-usb-0:1.2'

Arguments:
  - match (dict): key and value pairs for a udev match, see `udev Matching`_

A udev rules file may be needed to allow access for non-root users:

.. code-block:: none

   DRIVERS=="usbtmc", MODE="0660", GROUP="plugdev"

Used by:
  - `USBTMCDriver`_

NetworkUSBTMC
~~~~~~~~~~~~~
A :any:`NetworkUSBTMC` resource describes a `USBTMC`_ resource available
on a remote computer.

Flashrom
~~~~~~~~
A :any:`Flashrom` resource is used to configure the parameters to a local
installed flashrom instance.
It is assumed that flashrom is installed on the host and the executable is
configured in:

.. code-block:: yaml

  tools:
    flashrom: '/usr/sbin/flashrom'

Arguments:
  - programmer (str): programmer device as described in ``-p, --programmer`` in
    ``man 8 flashrom``

The resource must configure which programmer to use and the parameters to the
programmer.
The programmer parameter is passed directly to the flashrom bin hence
``man 8 flashrom`` can be used for reference.
Below an example where the local spidev is used.

.. code-block:: yaml

  Flashrom:
    programmer: 'linux_spi:dev=/dev/spidev0.1,spispeed=30000'

Used by:
  - `FlashromDriver`_

NetworkFlashrom
~~~~~~~~~~~~~~~
A :any:`NetworkFlashrom` describes a `Flashrom`_ available on a remote computer.

USBFlashableDevice
~~~~~~~~~~~~~~~~~~
A :any:`USBFlashableDevice` represents an "opaque" USB device used by custom
flashing programs.
There is usually not anything useful that can be done with the interface other
than running a flashing program with `FlashScriptDriver`_.

.. note::
   This resource is only intended to be used as a last resort when it is
   impossible or impractical to use a different resource

.. code-block:: yaml

   USBFlashableDevice:
     match:
       SUBSYSTEM: 'usb'
       ID_SERIAL: '1234'

Arguments:
  - match (dict): key and value pairs for a udev match, see `udev Matching`_

Used by:
  - `FlashScriptDriver`_

NetworkUSBFlashableDevice
~~~~~~~~~~~~~~~~~~~~~~~~~
A :any:`NetworkUSBFlashableDevice` resource describes a `USBFlashableDevice`_
resource available on a remote computer

DediprogFlasher
~~~~~~~~~~~~~~~
A :any:`DediprogFlasher` resource is used to configure the parameters to a
locally installed dpmcd instance.
It is assumed that dpcmd is installed on the host and the executable can be
configured via:

.. code-block:: yaml

  tools:
    dpcmd: '/usr/sbin/dpcmd'

Arguments:
  - vcc (str): ``3.5V``, ``2.5V`` or ``1.8V``.

For instance, to flash using 3.5 V VCC:

.. code-block:: yaml

  DediprogFlasher:
    vcc: '3.5V'

Used by:
  - `DediprogFlashDriver`_

NetworkDediprogFlasher
~~~~~~~~~~~~~~~~~~~~~~
A :any:`NetworkDediprogFlasher` describes a `DediprogFlasher`_ available on a
remote computer.

XenaManager
~~~~~~~~~~~
A :any:`XenaManager` resource describes a *Xena Manager* instance which is the
instance the `XenaDriver`_ must connect to in order to configure a Xena
chassis.

.. code-block:: yaml

   XenaManager:
     hostname: 'example.computer'

Arguments:
  - hostname (str): hostname or IP of the management address of the Xena tester

Used by:
  - `XenaDriver`_

PyVISADevice
~~~~~~~~~~~~
A :any:`PyVISADevice` resource describes a test stimuli device controlled by
PyVISA.
Such device could be a signal generator.

.. code-block:: yaml

   PyVISADevice:
     type: 'TCPIP'
     url: '192.168.110.11'

Arguments:
  - type (str): device resource type following the PyVISA resource syntax, e.g.
    ASRL, TCPIP...
  - url (str): device identifier on selected resource, e.g. <ip> for TCPIP
    resource
  - backend (str): optional, Visa library backend, e.g. '@sim' for pyvisa-sim backend

Used by:
  - `PyVISADriver`_

HTTPVideoStream
~~~~~~~~~~~~~~~
An :any:`HTTPVideoStream` resource describes an IP video stream over HTTP or HTTPS.

.. code-block:: yaml

   HTTPVideoStream:
     url: 'http://192.168.110.11/0.ts'

Arguments:
  - url (str): URI of the IP video stream

Used by:
  - `HTTPVideoDriver`_

USBHub
~~~~~~

A :any:`USBHub` resource describes an USB hub.
There is no corresponding driver, as this resource is only useful to monitor
whether the expected USB hubs are detected by an exporter.
To control individual ports, use `USBPowerPort`_.

.. code-block:: yaml

   USBHub:
     match:
       ID_PATH: 'pci-0000:02:00.0-usb-0:4:1.0'


Arguments:
  - match (dict): key and value pairs for a udev match, see `udev Matching`_

Used by:
  - none

Providers
~~~~~~~~~
Providers describe directories that are accessible by the target over a
specific protocol.
This is useful for software installation in the bootloader (via TFTP) or
downloading update artifacts under Linux (via HTTP).

They are used with the :any:`ManagedFile` helper, which ensures that the file
is available on the server. For HTTP and TFTP, a symlink from the internal
directory to the uploaded file is created.
The path for the target is generated by replacing the internal prefix with the
external prefix.
For NFS, it is assumed that ``/var/cache/labgrid`` is exported.
The information required for mounting and accessing staged files are returned,
see below.

For now, the TFTP/NFS/HTTP server needs to be configured before using it from
labgrid.

TFTPProvider
++++++++++++
A :any:`TFTPProvider` resource describes a TFTP server.

.. code-block:: yaml

   TFTPProvider:
     internal: '/srv/tftp/board-23/'
     external: 'board-23/'

Arguments:
  - internal (str): path prefix to the local directory accessible by the target
  - external (str): corresponding path prefix for use by the target

Used by:
  - `TFTPProviderDriver`_

HTTPProvider
++++++++++++
An :any:`HTTPProvider` resource describes an HTTP server.

.. code-block:: yaml

   HTTPProvider:
     internal: '/srv/www/board-23/'
     external: 'http://192.168.1.1/board-23/'

Arguments:
  - internal (str): path prefix to the local directory accessible by the target
  - external (str): corresponding path prefix for use by the target

Used by:
  - `HTTPProviderDriver`_

NFSProvider
+++++++++++
An :any:`NFSProvider` resource describes an NFS server.

.. code-block:: yaml

   NFSProvider: {}

Arguments:
  - None

Used by:
  - `NFSProviderDriver`_

RemoteTFTPProvider
++++++++++++++++++
A :any:`RemoteTFTPProvider` describes a `TFTPProvider`_ resource available on
a remote computer.

.. code-block:: yaml

   RemoteTFTPProvider
     host: 'tftphost'
     internal: '/srv/tftp/board-23/'
     external: 'board-23/'

Arguments:
  - host (str): hostname of the remote host
  - internal (str): path prefix to the TFTP root directory on ``host``
  - external (str): corresponding path prefix for use by the target

Used by:
  - `TFTPProviderDriver`_

RemoteHTTPProvider
++++++++++++++++++
A :any:`RemoteHTTPProvider` describes an `HTTPProvider`_ resource available on
a remote computer.

.. code-block:: yaml

   RemoteHTTPProvider:
     host: 'httphost'
     internal: '/srv/www/board-23/'
     external: 'http://192.168.1.1/board-23/'

Arguments:
  - host (str): hostname of the remote host
  - internal (str): path prefix to the HTTP root directory on ``host``
  - external (str): corresponding path prefix for use by the target

Used by:
  - `HTTPProviderDriver`_

RemoteNFSProvider
+++++++++++++++++
A :any:`RemoteNFSProvider` describes an `NFSProvider`_ resource available on a
remote computer.

.. code-block:: yaml

   RemoteNFSProvider:
     host: 'nfshost'

Arguments:
  - host (str): hostname of the remote host

Used by:
  - `NFSProviderDriver`_

RemotePlace
~~~~~~~~~~~
A :any:`RemotePlace` describes a set of resources attached to a labgrid remote
place.

.. code-block:: yaml

   RemotePlace:
     name: 'example-place'

The example describes the remote place ``example-place``. It will connect to the
labgrid remote coordinator, wait until the resources become available and expose
them to the internal environment.

Arguments:
  - name (str): name or pattern of the remote place

Used by:
  - potentially all drivers

DockerDaemon
~~~~~~~~~~~~
A :any:`DockerDaemon` describes where to contact a *docker daemon* process.
DockerDaemon also participates in managing `NetworkService`_ instances
created through interaction with that daemon.

.. code-block:: yaml

   DockerDaemon:
     docker_daemon_url: 'unix://var/run/docker.sock'

The example describes a docker daemon accessible via the
``/var/run/docker.sock`` unix socket. When used by a `DockerDriver`_, the
`DockerDriver`_ will first create a docker container which the
DockerDaemon resource will subsequently use to create one/more
`NetworkService`_ instances - as specified by `DockerDriver`_ configuration.
Each `NetworkService`_ instance corresponds to a network service running inside
the container.

Moreover, DockerDaemon will remove any hanging containers if
DockerDaemon is used several times in a row - as is the case when
executing test suites. Normally `DockerDriver`_ - when deactivated -
cleans up the created docker container; programming errors, keyboard
interrupts or unix kill signals may lead to hanging containers, however;
therefore auto-cleanup is important.

Arguments:
  - docker_daemon_url (str): url of the daemon to use for this target

Used by:
  - `DockerDriver`_

.. _udev-matching:

udev Matching
~~~~~~~~~~~~~
labgrid allows the exporter (or the client-side environment) to match resources
via udev rules.
Any udev property key and value can be used, path matching USB devices is
allowed as well.
The udev resources become available as soon as they are plugged into the
computer running the exporter.

The initial matching and monitoring for udev events is handled by the
:any:`UdevManager` class.
This manager is automatically created when a resource derived from
:any:`USBResource` (such as :any:`USBSerialPort`, :any:`IMXUSBLoader` or
:any:`AndroidUSBFastboot`) is instantiated.

To identify the kernel device which corresponds to a configured `USBResource`,
each existing (and subsequently added) kernel device is matched against the
configured resources.
This is based on a list of `match entries` which must all be tested
successfully against the potential kernel device.
Match entries starting with an ``@`` are checked against the device's parents
instead of itself; here one matching parent causes the check to be successful.

A given `USBResource` class has builtin match entries that are checked first,
for example that the ``SUBSYSTEM`` is ``tty`` as in the case of the
:any:`USBSerialPort`.
Only if these succeed, match entries provided by the user for the resource
instance are considered.

In addition to the properties reported by ``udevadm monitor --udev
--property``, elements of the ``ATTR(S){}`` dictionary (as shown by ``udevadm
info <device> -a``) are useable as match keys.
Finally ``sys_name`` allows matching against the name of the directory in
sysfs.
All match entries must succeed for the device to be accepted.

labgrid provides a small utility called ``labgrid-suggest`` which will
output the proper YAML formatted snippets for you.
These snippets can be added under the resource key in an environment
configuration or under their own entries in an exporter configuration file.

As the USB bus number can change depending on the kernel driver initialization
order, it is better to use the ``ID_PATH`` instead of ``sys_name`` for USB
devices.

In the default udev configuration, ``ID_PATH`` is not available for all USB
devices, but that can be changed by creating a udev rules file:

.. code-block:: none

  SUBSYSTEMS=="usb", IMPORT{builtin}="path_id"

The following examples show how to use the udev matches for some common
use-cases.

Matching a USB Serial Converter on a Hub Port
+++++++++++++++++++++++++++++++++++++++++++++
This will match any USB serial converter connected below the hub port 1.2.5.5
on bus 1.
The ``ID_PATH`` value corresponds to the hierarchy of buses and ports as shown
with ``udevadm info /dev/ttyUSB0``.

.. code-block:: yaml

  USBSerialPort:
    match:
      '@ID_PATH': 'pci-0000:05:00.0-usb-0:1.2.5.5'

Note the ``@`` in the ``@ID_PATH`` match, which applies this match to the
device's parents instead of directly to itself.
This is necessary for the `USBSerialPort`_ because we actually want to find the
``ttyUSB?`` device below the USB serial converter device.

Matching an Android USB Fastboot Device
+++++++++++++++++++++++++++++++++++++++
In this case, we want to match the USB device on that port directly, so we
don't use a parent match.

.. code-block:: yaml

  AndroidUSBFastboot:
    match:
      ID_PATH: 'pci-0000:05:00.0-usb-0:1.2.3'

Matching a Specific UART in a Dual-Port Adapter
+++++++++++++++++++++++++++++++++++++++++++++++
On this board, the serial console is connected to the second port of an
on-board dual-port USB-UART.
The board itself is connected to the bus 3 and port path ``10.2.2.2``.
The correct value can be shown by running ``udevadm info /dev/ttyUSB9`` in our
case:

.. code-block:: bash
  :emphasize-lines: 21

  $ udevadm info /dev/ttyUSB9
  P: /devices/pci0000:00/0000:00:14.0/usb3/3-10/3-10.2/3-10.2.2/3-10.2.2.2/3-10.2.2.2:1.1/ttyUSB9/tty/ttyUSB9
  N: ttyUSB9
  S: serial/by-id/usb-FTDI_Dual_RS232-HS-if01-port0
  S: serial/by-path/pci-0000:00:14.0-usb-0:10.2.2.2:1.1-port0
  E: DEVLINKS=/dev/serial/by-id/usb-FTDI_Dual_RS232-HS-if01-port0 /dev/serial/by-path/pci-0000:00:14.0-usb-0:10.2.2.2:1.1-port0
  E: DEVNAME=/dev/ttyUSB9
  E: DEVPATH=/devices/pci0000:00/0000:00:14.0/usb3/3-10/3-10.2/3-10.2.2/3-10.2.2.2/3-10.2.2.2:1.1/ttyUSB9/tty/ttyUSB9
  E: ID_BUS=usb
  E: ID_MODEL=Dual_RS232-HS
  E: ID_MODEL_ENC=Dual\x20RS232-HS
  E: ID_MODEL_FROM_DATABASE=FT2232C Dual USB-UART/FIFO IC
  E: ID_MODEL_ID=6010
  E: ID_PATH=pci-0000:00:14.0-usb-0:10.2.2.2:1.1
  E: ID_PATH_TAG=pci-0000_00_14_0-usb-0_10_2_2_2_1_1
  E: ID_REVISION=0700
  E: ID_SERIAL=FTDI_Dual_RS232-HS
  E: ID_TYPE=generic
  E: ID_USB_DRIVER=ftdi_sio
  E: ID_USB_INTERFACES=:ffffff:
  E: ID_USB_INTERFACE_NUM=01
  E: ID_VENDOR=FTDI
  E: ID_VENDOR_ENC=FTDI
  E: ID_VENDOR_FROM_DATABASE=Future Technology Devices International, Ltd
  E: ID_VENDOR_ID=0403
  E: MAJOR=188
  E: MINOR=9
  E: SUBSYSTEM=tty
  E: TAGS=:systemd:
  E: USEC_INITIALIZED=9129609697

We use the ``ID_USB_INTERFACE_NUM`` to distinguish between the two ports:

.. code-block:: yaml

  USBSerialPort:
    match:
      '@ID_PATH': 'pci-0000:05:00.0-usb-2:10.2.2.2'
      ID_USB_INTERFACE_NUM: '01'

Matching a USB UART by Serial Number
++++++++++++++++++++++++++++++++++++
Most of the USB serial converters in our lab have been programmed with unique
serial numbers.
This makes it easy to always match the same one even if the USB topology
changes or a board has been moved between host systems.

.. code-block:: yaml

  USBSerialPort:
    match:
      ID_SERIAL_SHORT: 'P-00-03564'

To check if your device has a serial number, you can use ``udevadm info``:

.. code-block:: bash

  $ udevadm info /dev/ttyUSB5 | grep SERIAL_SHORT
  E: ID_SERIAL_SHORT=P-00-03564

In the background, the additional properties are provided by the builtin ``usb_id``
udev helper::

  $ udevadm test-builtin usb_id /sys/class/tty/ttyUSB0
  Load module index
  Parsed configuration file /lib/systemd/network/99-default.link
  Parsed configuration file /lib/systemd/network/73-usb-net-by-mac.link
  Created link configuration context.
  ID_VENDOR=Silicon_Labs
  ID_VENDOR_ENC=Silicon\x20Labs
  ID_VENDOR_ID=10c4
  ID_MODEL=CP2102_USB_to_UART_Bridge_Controller
  ID_MODEL_ENC=CP2102\x20USB\x20to\x20UART\x20Bridge\x20Controller
  ID_MODEL_ID=ea60
  ID_REVISION=0100
  ID_SERIAL=Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_P-00-03564
  ID_SERIAL_SHORT=P-00-03564
  ID_TYPE=generic
  ID_BUS=usb
  ID_USB_INTERFACES=:ff0000:
  ID_USB_INTERFACE_NUM=00
  ID_USB_DRIVER=cp210x
  Unload module index
  Unloaded link configuration context.

Drivers
-------

SerialDriver
~~~~~~~~~~~~
A :any:`SerialDriver` connects to a serial port. It requires one of the serial
port resources.

Binds to:
  port:
    - `NetworkSerialPort`_
    - `RawSerialPort`_
    - `USBSerialPort`_

.. code-block:: yaml

   SerialDriver:
     txdelay: 0.05

Implements:
  - :any:`ConsoleProtocol`
  - :any:`ResetProtocol`

Arguments:
  - txdelay (float, default=0.0): time in seconds to wait before sending each byte
  - timeout (float, default=3.0): time in seconds to wait for a network serial port before
    an error occurs

ModbusRTUDriver
~~~~~~~~~~~~~~~
A :any:`ModbusRTUDriver` connects to a ModbusRTU resource. This driver only
supports local usage and will not work with an exporter.

The driver is implemented using the
`minimalmodbus <https://minimalmodbus.readthedocs.io/en/stable/>`_ Python
library.
The implementation only supports that labgrid will be the master on the Modbus
network.

.. code-block:: yaml

    ModbusRTUDriver: {}

Binds to:
  resource:
    - `ModbusRTU`_

Implements:
  - None (yet)

Arguments:
  - None

ShellDriver
~~~~~~~~~~~
A :any:`ShellDriver` binds on top of a :any:`ConsoleProtocol` and is designed
to interact with a login prompt and a Linux shell.

Binds to:
  console:
    - :any:`ConsoleProtocol`

Implements:
  - :any:`CommandProtocol`
  - :any:`FileTransferProtocol`

.. code-block:: yaml

   ShellDriver:
     prompt: 'root@[\w-]+:[^ ]+ '
     login_prompt: ' login: '
     username: 'root'

Arguments:
  - prompt (regex): shell prompt to match after logging in
  - login_prompt (regex): match for the login prompt
  - username (str): username to use during login
  - password (str): optional, password to use during login.
    Can be an empty string.
  - keyfile (str): optional, keyfile to upload after login, making the
    `SSHDriver`_ usable
  - login_timeout (int, default=60): timeout for login prompt detection in
    seconds
  - await_login_timeout (int, default=2): time in seconds of silence that needs
    to pass before sending a newline to device.
  - console_ready (regex): optional, pattern used by the kernel to inform
    the user that a console can be activated by pressing enter.
  - post_login_settle_time (int, default=0): seconds of silence after logging in
    before check for a prompt. Useful when the console is interleaved with boot
    output which may interrupt prompt detection.

.. note::
   `bash >= 5.1 <https://www.gnu.org/software/bash/manual/bash.html#index-enable_002dbracketed_002dpaste>`_
   enables bracketed-paste mode by default,
   allowing the terminal emulator to tell a program whether input was typed or
   pasted.
   To achieve this, ``\e[?2004h`` is inserted when user input is expected,
   enabling paste detection.

   Add ``\x1b\[\?2004h`` at the beginning of the prompt argument to allow the
   ShellDriver to still match the prompt in this case.

.. _conf-sshdriver:

SSHDriver
~~~~~~~~~
An :any:`SSHDriver` requires a `NetworkService`_ resource and allows the
execution of commands and file upload via network.
It uses SSH's ``ServerAliveInterval`` option to detect failed connections.

If a shared SSH connection to the target is already open, it will reuse it when
running commands.
In that case, ``ServerAliveInterval`` should be set outside of labgrid, as it
cannot be enabled for an existing connection.

Binds to:
  networkservice:
    - `NetworkService`_

Implements:
  - :any:`CommandProtocol`
  - :any:`FileTransferProtocol`

.. code-block:: yaml

   SSHDriver:
     keyfile: 'example.key'

Arguments:
  - keyfile (str): optional, filename of private key to login into the remote system
    (has precedence over `NetworkService`_'s password)
  - stderr_merge (bool, default=False): set to True to make ``run()`` return stderr merged with
    stdout, and an empty list as second element.
  - connection_timeout (float, default=30.0): timeout when trying to establish connection to
    target.
  - explicit_sftp_mode (bool, default=False): if set to True, ``put()``, ``get()``, and ``scp()``
    will explicitly use the SFTP protocol for file transfers instead of scp's default protocol
  - explicit_scp_mode (bool, default=False): if set to True, ``put()``, ``get()``, and ``scp()``
    will explicitly use the SCP protocol for file transfers instead of scp's default protocol
  - username (str, default=username from `NetworkService`_): username used by SSH
  - password (str, default=password from `NetworkService`_): password used by SSH

UBootDriver
~~~~~~~~~~~
A :any:`UBootDriver` interfaces with a U-Boot bootloader via a
:any:`ConsoleProtocol`.

Binds to:
  console:
    - :any:`ConsoleProtocol`

Implements:
  - :any:`CommandProtocol`
  - :any:`LinuxBootProtocol`

.. code-block:: yaml

   UBootDriver:
     prompt: 'Uboot> '
     boot_commands:
       net: 'run netboot'
       spi: 'run spiboot'

Arguments:
  - prompt (regex, default=""): U-Boot prompt to match
  - autoboot (regex, default="stop autoboot"): autoboot message to match
  - password (str): optional, U-Boot unlock password
  - interrupt (str, default="\\n"): string to interrupt autoboot (use ``\\x03`` for CTRL-C)
  - init_commands (tuple): optional, tuple of commands to execute after matching the
    prompt
  - password_prompt (str, default="enter Password: "): regex to match the U-Boot password prompt
  - bootstring (str): optional, regex to match on Linux Kernel boot
  - boot_command (str, default="run bootcmd"): boot command for booting target
  - boot_commands (dict, default={}): boot commands by name for LinuxBootProtocol boot command
  - login_timeout (int, default=30): timeout for login prompt detection in seconds
  - boot_timeout (int, default=30): timeout for initial Linux Kernel version detection

SmallUBootDriver
~~~~~~~~~~~~~~~~
A :any:`SmallUBootDriver` interfaces with stripped-down *U-Boot* variants that
are sometimes used in cheap consumer electronics.

SmallUBootDriver is meant as a driver for U-Boot with only little functionality
compared to a standard U-Boot.
Especially is copes with the following limitations:

- The U-Boot does not have a real password-prompt but can be activated by
  entering a "secret" after a message was displayed.
- The command line does not have a built-in echo command.
  Thus this driver uses "Unknown Command" messages as marker before and after
  the output of a command.
- Since there is no echo we cannot return the exit code of the command.
  Commands will always return 0 unless the command was not found.

This driver needs the following features activated in U-Boot to work:

- The U-Boot must not have a real password prompt. Instead it must be keyword
  activated.
  For example it should be activated by a dialog like the following:

  - U-Boot: "Autobooting in 1s..."
  - labgrid: "secret"
  - U-Boot: <switching to console>

- The U-Boot must be able to parse multiple commands in a single line separated
  by ";".
- The U-Boot must support the "bootm" command to boot from a memory location.

Binds to:
  console:
    - :any:`ConsoleProtocol` (see `SerialDriver`_)

Implements:
  - :any:`CommandProtocol`
  - :any:`LinuxBootProtocol`

.. code-block:: yaml

   SmallUBootDriver:
     prompt: 'ap143-2\.0> '
     boot_expression: 'Autobooting in 1 seconds'
     boot_secret: 'tpl'

Arguments:
  - boot_expression (str, default="U-Boot 20\\d+"): regex to match the U-Boot start string
  - boot_secret (str, default="a"): secret used to unlock prompt
  - boot_secret_nolf (bool, default=False): send boot_secret without new line
  - login_timeout (int, default=60): timeout for password/login prompt detection
  - for other arguments, see `UBootDriver`_

BareboxDriver
~~~~~~~~~~~~~
A :any:`BareboxDriver` interfaces with a *barebox* bootloader via a
:any:`ConsoleProtocol`.

Binds to:
  console:
    - :any:`ConsoleProtocol`

Implements:
  - :any:`CommandProtocol`
  - :any:`LinuxBootProtocol`

.. code-block:: yaml

   BareboxDriver:
     prompt: 'barebox@[^:]+:[^ ]+ '

Arguments:
  - prompt (regex, default=""): barebox prompt to match
  - autoboot (regex, default="stop autoboot"): autoboot message to match
  - interrupt (str, default="\\n"): string to interrupt autoboot (use "\\x03" for CTRL-c),
    `CTRL-d <https://git.pengutronix.de/cgit/barebox/commit/?id=ae482477b60e1e308327658a899358746ff2f5b>`_
    ("\\x04") is recommended to ensure barebox behaves as closely as possible to uninterrupted
    boots (for barebox >=v2025.03.0).
  - bootstring (regex, default="Linux version \\d"): regex that indicating that the Linux Kernel is
    booting
  - password (str): optional, password to use for access to the shell
  - login_timeout (int, default=60): timeout for access to the shell

ExternalConsoleDriver
~~~~~~~~~~~~~~~~~~~~~
An :any:`ExternalConsoleDriver` implements the :any:`ConsoleProtocol` on top of
a command executed on the local computer.

Binds to:
  - None

Implements:
  - :any:`ConsoleProtocol`

.. code-block:: yaml

   ExternalConsoleDriver:
     cmd: 'microcom /dev/ttyUSB2'
     txdelay: 0.05

Arguments:
  - cmd (str): command to execute and then bind to.
  - txdelay (float, default=0.0): time in seconds to wait before sending each byte

AndroidFastbootDriver
~~~~~~~~~~~~~~~~~~~~~
An :any:`AndroidFastbootDriver` allows the upload of images to a device in the
USB or network *Fastboot state*.

Binds to:
  fastboot:
    - `AndroidUSBFastboot`_
    - RemoteAndroidUSBFastboot
    - `AndroidNetFastboot`_
    - RemoteAndroidNetFastboot

Implements:
  - None (yet)

.. code-block:: yaml

   AndroidFastbootDriver:
     boot_image: 'mylocal.image'
     sparse_size: '100M'

Arguments:
  - boot_image (str): optional, image key referring to the image to boot
  - flash_images (dict): optional, partition to image key mapping referring to
    images to flash to the device
  - sparse_size (str): optional, sparse files greater than given size (see
    fastboot manpage -S option for allowed size suffixes). The default is the
    same as the fastboot default, which is computed after querying the target's
    ``max-download-size`` variable.

DFUDriver
~~~~~~~~~
A :any:`DFUDriver` allows the download of images to a device in DFU (Device
Firmware Upgrade) mode.

Binds to:
  dfu:
    - `DFUDevice`_
    - NetworkDFUDevice

Implements:
  - None (yet)

.. code-block:: yaml

   DFUDriver: {}

Arguments:
  - None

OpenOCDDriver
~~~~~~~~~~~~~
An :any:`OpenOCDDriver` controls *OpenOCD* to bootstrap a target with a
bootloader.

Note that OpenOCD supports specifying USB paths since
`a1b308ab <https://sourceforge.net/p/openocd/code/ci/a1b308ab/>`_ which was released with v0.11.
The OpenOCDDriver passes the resource's USB path.
Depending on which OpenOCD version is installed it is either used correctly or
a warning is displayed and the first resource seen is used, which might be the
wrong USB device.
Consider updating your OpenOCD version when using multiple USB Blasters.

Binds to:
  interface:
    - `AlteraUSBBlaster`_
    - NetworkAlteraUSBBlaster
    - `USBDebugger`_
    - NetworkUSBDebugger

Implements:
  - :any:`BootstrapProtocol`

.. code-block:: yaml

   OpenOCDDriver:
     config: 'local-settings.cfg'
     image: 'bitstream'
     interface_config: 'ftdi/lambdaconcept_ecpix-5.cfg'
     board_config: 'lambdaconcept_ecpix-5.cfg'
     load_commands:
     - 'init'
     - 'svf -quiet {filename}'
     - 'exit'

Arguments:
  - config (str/list): optional, OpenOCD configuration file(s)
  - search (str): optional, include search path for scripts
  - image (str): optional, name of the image to bootstrap onto the device
  - interface_config (str): optional, interface config in the ``openocd/scripts/interface/`` directory
  - board_config (str): optional, board config in the ``openocd/scripts/board/`` directory
  - load_commands (list of str): optional, load commands to use instead of ``init``, ``bootstrap {filename}``, ``shutdown``

QuartusHPSDriver
~~~~~~~~~~~~~~~~
A :any:`QuartusHPSDriver` controls the "Quartus Prime Programmer and Tools" to
flash a target's QSPI.

Binds to:
  interface:
    - `AlteraUSBBlaster`_
    - NetworkAlteraUSBBlaster

Implements:
  - None

Arguments:
  - image (str): optional, filename of image to write into QSPI flash

The driver can be used in test cases by calling its ``flash()`` method. An
example strategy is included in labgrid.

ManualPowerDriver
~~~~~~~~~~~~~~~~~
A :any:`ManualPowerDriver` requires the user to control the target power
states.
This is required if a strategy is used with the target, but no automatic power
control is available.

The driver's name will be displayed during interaction.

Binds to:
  - None

Implements:
  - :any:`PowerProtocol`
  - :any:`ResetProtocol`

.. code-block:: yaml

   ManualPowerDriver:
     name: 'example-board'

Arguments:
  - None

ExternalPowerDriver
~~~~~~~~~~~~~~~~~~~
An :any:`ExternalPowerDriver` is used to control a target power state via an
external command.

Binds to:
  - None

Implements:
  - :any:`PowerProtocol`
  - :any:`ResetProtocol`

.. code-block:: yaml

   ExternalPowerDriver:
     cmd_on: 'example_command on'
     cmd_off: 'example_command off'
     cmd_cycle: 'example_command cycle'

Arguments:
  - cmd_on (str): command to turn power to the board on
  - cmd_off (str): command to turn power to the board off
  - cmd_cycle (str): optional command to switch the board off and on
  - delay (float, default=2.0): delay in seconds between off and on, if cmd_cycle is not set

NetworkPowerDriver
~~~~~~~~~~~~~~~~~~
A :any:`NetworkPowerDriver` controls a `NetworkPowerPort`_, allowing control of
the target power state without user interaction.

Binds to:
  port:
    - `NetworkPowerPort`_

Implements:
  - :any:`PowerProtocol`
  - :any:`ResetProtocol`

.. code-block:: yaml

   NetworkPowerDriver:
     delay: 5.0

Arguments:
  - delay (float, default=2.0): delay in seconds between off and on

PDUDaemonDriver
~~~~~~~~~~~~~~~
A :any:`PDUDaemonDriver` controls a `PDUDaemonPort`_, allowing control of the
target power state without user interaction.

.. note::
  PDUDaemon processes commands in the background, so the actual state change
  may happen several seconds after calls to PDUDaemonDriver return.

Binds to:
  port:
    - `PDUDaemonPort`_

Implements:
  - :any:`PowerProtocol`
  - :any:`ResetProtocol`

.. code-block:: yaml

   PDUDaemonDriver:
     delay: 5.0

Arguments:
  - delay (float, default=5.0): delay in seconds between off and on

YKUSHPowerDriver
~~~~~~~~~~~~~~~~
A :any:`YKUSHPowerDriver` controls a `YKUSHPowerPort`_, allowing control of the
target power state without user interaction.

Binds to:
  port:
    - `YKUSHPowerPort`_
    - `NetworkYKUSHPowerPort`_

Implements:
  - :any:`PowerProtocol`
  - :any:`ResetProtocol`

.. code-block:: yaml

   YKUSHPowerDriver:
     delay: 5.0

Arguments:
  - delay (float, default=2.0): delay in seconds between off and on

DigitalOutputPowerDriver
~~~~~~~~~~~~~~~~~~~~~~~~
A :any:`DigitalOutputPowerDriver` can be used to control the power of a device
using a DigitalOutputDriver.

Using this driver you probably want an external relay to switch the
power of your DUT.

Binds to:
  output:
    - :any:`DigitalOutputProtocol`

Implements:
  - :any:`PowerProtocol`
  - :any:`ResetProtocol`

.. code-block:: yaml

   DigitalOutputPowerDriver:
     delay: 2.0

Arguments:
  - delay (float, default=1.0): delay in seconds between off and on

USBPowerDriver
~~~~~~~~~~~~~~
A :any:`USBPowerDriver` controls a `USBPowerPort`_, allowing control of the
target power state without user interaction.

Binds to:
  hub:
    - `USBPowerPort`_
    - NetworkUSBPowerPort

Implements:
  - :any:`PowerProtocol`
  - :any:`ResetProtocol`

.. code-block:: yaml

   USBPowerDriver:
     delay: 5.0

Arguments:
  - delay (float, default=2.0): delay in seconds between off and on

SiSPMPowerDriver
~~~~~~~~~~~~~~~~
A :any:`SiSPMPowerDriver` controls a `SiSPMPowerPort`_, allowing control of the
target power state without user interaction.

Binds to:
  port:
    - `SiSPMPowerPort`_
    - NetworkSiSPMPowerPort

Implements:
  - :any:`PowerProtocol`
  - :any:`ResetProtocol`

.. code-block:: yaml

   SiSPMPowerDriver:
     delay: 5.0

Arguments:
  - delay (float, default=2.0): delay in seconds between off and on

TasmotaPowerDriver
~~~~~~~~~~~~~~~~~~
A :any:`TasmotaPowerDriver` controls a `TasmotaPowerPort`_, allowing the outlet
to be switched on and off.

Binds to:
  power:
    - `TasmotaPowerPort`_

Implements:
  - :any:`PowerProtocol`

.. code-block:: yaml

   TasmotaPowerDriver:
     delay: 5.0

Arguments:
  - delay (float, default=2.0): delay in seconds between off and on

GpioDigitalOutputDriver
~~~~~~~~~~~~~~~~~~~~~~~
The :any:`GpioDigitalOutputDriver` writes a digital signal to a GPIO line.

This driver configures GPIO lines via `the sysfs kernel interface <https://www.kernel.org/doc/html/latest/gpio/sysfs.html>`.
While the driver automatically exports the GPIO, it does not configure it in any other way than as an output.

Binds to:
  gpio:
    - `SysfsGPIO`_
    - `MatchedSysfsGPIO`_
    - NetworkSysfsGPIO

Implements:
  - :any:`DigitalOutputProtocol`

.. code-block:: yaml

   GpioDigitalOutputDriver: {}

Arguments:
  - None

SerialPortDigitalOutputDriver
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The :any:`SerialPortDigitalOutputDriver` makes it possible to use a UART
as a 1-Bit general-purpose digital output.

This driver acts on top of a SerialDriver and uses the its pyserial port to
control the flow control lines.

Binds to:
  serial:
    - `SerialDriver`_

Implements:
  - :any:`DigitalOutputProtocol`

.. code-block:: yaml

   SerialPortDigitalOutputDriver:
     signal: 'dtr'
     invert: false
     bindings:
       serial: 'nameOfSerial'

Arguments:
  - signal (str): control signal to use: "dtr" or "rts"
  - invert (bool): whether to invert the signal
  - bindings (dict): optional, a named resource of the type SerialDriver to
    bind against. This is only needed if you have multiple
    SerialDriver in your environment (what is likely to be the case
    if you are using this driver).

FileDigitalOutputDriver
~~~~~~~~~~~~~~~~~~~~~~~
The :any:`FileDigitalOutputDriver` uses a file
to write arbitrary string representations of booleans
to a file and read from it.

The file is checked to exist at configuration time.

If the file's content does not match any of the representations
reading defaults to False.

A prime example for using this driver is Linux's sysfs.

Binds to:
  - None

Implements:
  - :any:`DigitalOutputProtocol`

.. code-block:: yaml

   FileDigitalOutputDriver:
     filepath: '/sys/class/leds/myled/brightness'

Arguments:
  - filepath (str): file that is used for reads and writes.
  - false_repr (str, default="0\\n"): representation for False
  - true_repr (str, default="1\\n"): representation for True

DigitalOutputResetDriver
~~~~~~~~~~~~~~~~~~~~~~~~
A :any:`DigitalOutputResetDriver` uses a DigitalOutput to reset the target.

Binds to:
  output:
    - :any:`DigitalOutputProtocol`

Implements:
  - :any:`ResetProtocol`

.. code-block:: yaml

   DigitalOutputResetDriver:
     delay: 2.0

Arguments:
  - delay (float, default=1.0): delay in seconds between setting the output 0 and 1.

ModbusCoilDriver
~~~~~~~~~~~~~~~~
A :any:`ModbusCoilDriver` controls a `ModbusTCPCoil`_ resource.
It can set and get the current state of the resource.

Binds to:
  coil:
    - `ModbusTCPCoil`_

Implements:
  - :any:`DigitalOutputProtocol`

.. code-block:: yaml

   ModbusCoilDriver: {}

Arguments:
  - None

HIDRelayDriver
~~~~~~~~~~~~~~
An :any:`HIDRelayDriver` controls an `HIDRelay`_ or `NetworkHIDRelay`_ resource.
It can set and get the current state of the resource.

Binds to:
  relay:
    - `HIDRelay`_
    - `NetworkHIDRelay`_

Implements:
  - :any:`DigitalOutputProtocol`

.. code-block:: yaml

   HIDRelayDriver: {}

Arguments:
  - None

ManualSwitchDriver
~~~~~~~~~~~~~~~~~~
A :any:`ManualSwitchDriver` requires the user to control a switch or jumper on
the target.
This can be used if a driver binds to a :any:`DigitalOutputProtocol`, but no
automatic control is available.

Binds to:
  - None

Implements:
  - :any:`DigitalOutputProtocol`

.. code-block:: yaml

   ManualSwitchDriver:
     description: 'Jumper 5'

Arguments:
  - description (str): optional, description of the switch or jumper on the target

DeditecRelaisDriver
~~~~~~~~~~~~~~~~~~~
A :any:`DeditecRelaisDriver` controls a *Deditec* relay resource.
It can set and get the current state of the resource.

Binds to:
  relais:
    - `DeditecRelais8`_
    - NetworkDeditecRelais8

Implements:
  - :any:`DigitalOutputProtocol`

.. code-block:: yaml

   DeditecRelaisDriver: {}

Arguments:
  - None

MXSUSBDriver
~~~~~~~~~~~~
An :any:`MXSUSBDriver` is used to upload an image into a device in the *MXS USB
loader state*.
This is useful to bootstrap a bootloader onto a device.

Binds to:
  loader:
    - `MXSUSBLoader`_
    - `NetworkMXSUSBLoader`_

Implements:
  - :any:`BootstrapProtocol`

.. code-block:: yaml

   targets:
     main:
       drivers:
         MXSUSBDriver:
           image: 'mybootloaderkey'

   images:
     mybootloaderkey: 'path/to/mybootloader.img'

Arguments:
  - image (str): optional, key in :ref:`images <labgrid-device-config-images>` containing the path
    of an image to bootstrap onto the target

IMXUSBDriver
~~~~~~~~~~~~
An :any:`IMXUSBDriver` is used to upload an image into a device in the *i.MX
USB loader state*.
This is useful to bootstrap a bootloader onto a device.
This driver uses the ``imx-usb-loader`` tool from barebox.

Binds to:
  loader:
    - `IMXUSBLoader`_
    - `NetworkIMXUSBLoader`_
    - `MXSUSBLoader`_
    - `NetworkMXSUSBLoader`_

Implements:
  - :any:`BootstrapProtocol`

.. code-block:: yaml

   targets:
     main:
       drivers:
         IMXUSBDriver:
           image: 'mybootloaderkey'

   images:
     mybootloaderkey: 'path/to/mybootloader.img'

Arguments:
  - image (str): optional, key in :ref:`images <labgrid-device-config-images>` containing the path
    of an image to bootstrap onto the target

BDIMXUSBDriver
~~~~~~~~~~~~~~
The :any:`BDIMXUSBDriver` is used to upload bootloader images into an *i.MX
device* in the *USB SDP mode*.
This driver uses the ``imx_usb`` tool by Boundary Devices.
Compared to the ``imx-usb-loader``, it supports two-stage upload of U-Boot
images.
The images paths need to be specified from code instead of in the YAML
environment, as the correct image depends on the system state.

Binds to:
  loader:
    - `IMXUSBLoader`_
    - `NetworkIMXUSBLoader`_

Implements:
  - :any:`BootstrapProtocol`

.. code-block:: yaml

   targets:
     main:
       drivers:
         BDIMXUSBDriver: {}

Arguments:
  - None

RKUSBDriver
~~~~~~~~~~~
An :any:`RKUSBDriver` is used to upload an image into a device in the *Rockchip
USB loader state*.
This is useful to bootstrap a bootloader onto a device.

Binds to:
  loader:
    - `RKUSBLoader`_
    - `NetworkRKUSBLoader`_

Implements:
  - :any:`BootstrapProtocol`

.. code-block:: yaml

   targets:
     main:
       drivers:
         RKUSBDriver:
           image: 'mybootloaderkey'
           usb_loader: 'myloaderkey'

   images:
     mybootloaderkey: 'path/to/mybootloader.img'
     myloaderkey: 'path/to/myloader.bin'

Arguments:
  - image (str): optional, key in :ref:`images <labgrid-device-config-images>` containing the path
    of an image to bootstrap onto the target
  - usb_loader (str): optional, key in :ref:`images <labgrid-device-config-images>` containing the path
    of a first-stage bootloader image to write

UUUDriver
~~~~~~~~~
A :any:`UUUDriver` is used to upload an image into a device in the *NXP USB
loader state*.
This is useful to bootstrap a bootloader onto a device.

Binds to:
  loader:
    - `MXSUSBLoader`_
    - `NetworkMXSUSBLoader`_
    - `IMXUSBLoader`_
    - `NetworkIMXUSBLoader`_

Implements:
  - :any:`BootstrapProtocol`

.. code-block:: yaml

   targets:
     main:
       drivers:
         UUUDriver:
           image: 'mybootloaderkey'
           script: 'spl'

   images:
     mybootloaderkey: 'path/to/mybootloader.img'

Arguments:
  - image (str): optional, key in :ref:`images <labgrid-device-config-images>` containing the path
    of an image to bootstrap onto the target
  - script (str): optional, run built-in script with ``uuu -b``, called with image as arg0

USBStorageDriver
~~~~~~~~~~~~~~~~
A :any:`USBStorageDriver` allows access to a USB stick or similar local or
remote device.

Binds to:
  storage:
    - `USBMassStorage`_
    - `NetworkUSBMassStorage`_
    - `USBSDMuxDevice`_
    - `NetworkUSBSDMuxDevice`_
    - `USBSDWireDevice`_
    - `NetworkUSBSDWireDevice`_

Implements:
  - None (yet)

.. code-block:: yaml

   USBStorageDriver:
     image: 'flashimage'

.. code-block:: yaml

   images:
     flashimage: '../images/myusb.image'

Arguments:
  - image (str): optional, key in :ref:`images <labgrid-device-config-images>` containing the path
    of an image to write to the target

OneWirePIODriver
~~~~~~~~~~~~~~~~
A :any:`OneWirePIODriver` controls a `OneWirePIO`_ resource.
It can set and get the current state of the resource.

Binds to:
  port:
    - `OneWirePIO`_

Implements:
  - :any:`DigitalOutputProtocol`

.. code-block:: yaml

   OneWirePIODriver: {}

Arguments:
  - None

TFTPProviderDriver
~~~~~~~~~~~~~~~~~~
The :any:`TFTPProviderDriver` controls its corresponding TFTP resource, either
locally or remotely.

Binds to:
  provider:
    - `TFTPProvider`_
    - `RemoteTFTPProvider`_

Implements:
  - None (yet)

.. code-block:: yaml

   TFTPProviderDriver: {}

Arguments:
  - None

The driver can be used in test cases by calling its ``stage()`` method, which
returns the path to be used by the target.

HTTPProviderDriver
~~~~~~~~~~~~~~~~~~
The :any:`HTTPProviderDriver` controls its corresponding HTTP resource, either
locally or remotely.

Binds to:
  provider:
    - `HTTPProvider`_
    - `RemoteHTTPProvider`_

Implements:
  - None (yet)

.. code-block:: yaml

   HTTPProviderDriver: {}

Arguments:
  - None

The driver can be used in test cases by calling its ``stage()`` method, which
returns the path to be used by the target.

NFSProviderDriver
~~~~~~~~~~~~~~~~~
An :any:`NFSProviderDriver` controls an `NFSProvider`_ resource.

Binds to:
  provider:
    - `NFSProvider`_
    - `RemoteNFSProvider`_

Implements:
  - None (yet)

.. code-block:: yaml

   NFSProviderDriver: {}

Arguments:
  - None

The driver can be used in test cases by calling its ``stage()`` method, which
returns an NFSFile object with ``host``, ``export`` and ``relative_file_path``
attributes.

QEMUDriver
~~~~~~~~~~
The :any:`QEMUDriver` allows the usage of a QEMU instance as a target.
It requires several arguments, listed below.
The kernel, flash, rootfs and dtb arguments refer to images and paths declared
in the environment configuration.

Binds to:
  - None

.. code-block:: yaml

   QEMUDriver:
     qemu_bin: 'qemu_arm'
     machine: 'vexpress-a9'
     cpu: 'cortex-a9'
     memory: '512M'
     boot_args: 'root=/dev/root console=ttyAMA0,115200'
     extra_args: ''
     kernel: 'kernel'
     rootfs: 'rootfs'
     dtb: 'dtb'
     nic: 'user'

.. code-block:: yaml

   tools:
     qemu_arm: '/bin/qemu-system-arm'
   paths:
     rootfs: '../images/root'
   images:
     dtb: '../images/mydtb.dtb'
     kernel: '../images/vmlinuz'

Implements:
  - :any:`ConsoleProtocol`
  - :any:`PowerProtocol`

Arguments:
  - qemu_bin (str): reference to the tools key for the QEMU binary
  - machine (str): QEMU machine type
  - cpu (str): QEMU cpu type
  - memory (str): QEMU memory size (ends with M or G)
  - extra_args (str): optional, extra QEMU arguments, they are passed directly to the QEMU binary
  - boot_args (str): optional, additional kernel boot argument
  - kernel (str): optional, reference to the images key for the kernel
  - disk (str): optional, reference to the images key for the disk image
  - disk_opts (str): optional, additional QEMU disk options
  - flash (str): optional, reference to the images key for the flash image
  - rootfs (str): optional, reference to the paths key for use as the virtio-9p filesystem
  - dtb (str): optional, reference to the image key for the device tree
  - bios (str): optional, reference to the image key for the bios image
  - display (str, default="none"): display output to enable; must be one of:

    - none: Do not create a display device
    - fb-headless: Create a headless framebuffer device
    - egl-headless: Create a headless GPU-backed graphics card. Requires host support
    - qemu-default: Don't override QEMU default settings

  - nic (str): optional, configuration string to pass to QEMU to create a network interface

The QEMUDriver also requires the specification of:

- a tool key, this contains the path to the QEMU binary
- an image key, the path to the kernel image and optionally the dtb key to
  specify the build device tree
- a path key, this is the path to the rootfs

SigrokDriver
~~~~~~~~~~~~
The :any:`SigrokDriver` uses a `SigrokDevice`_ resource to record samples and provides
them during test runs.

Binds to:
  sigrok:
    - `SigrokUSBDevice`_
    - `NetworkSigrokUSBDevice`_
    - `SigrokDevice`_

Implements:
  - None yet

Arguments:
  - None

The driver can be used in test cases by calling its ``capture()``, ``stop()``
and ``analyze()`` methods.

SigrokPowerDriver
~~~~~~~~~~~~~~~~~
The :any:`SigrokPowerDriver` uses a `SigrokUSBSerialDevice`_ resource to
control a programmable power supply.

Binds to:
  sigrok:
    - `SigrokUSBSerialDevice`_
    - NetworkSigrokUSBSerialDevice

Implements:
  - :any:`PowerProtocol`
  - :any:`ResetProtocol`

.. code-block:: yaml

   SigrokPowerDriver:
     delay: 3.0

Arguments:
  - delay (float, default=3.0): delay in seconds between off and on
  - max_voltage (float): optional, maximum allowed voltage for protection against
    accidental damage (in volts)
  - max_current (float): optional, maximum allowed current for protection against
    accidental damage (in ampere)

SigrokDmmDriver
~~~~~~~~~~~~~~~
The :any:`SigrokDmmDriver` uses a `SigrokDevice`_ resource to record samples
from a *digital multimeter* (DMM) and provides them during test runs.

It is known to work with *Unit-T UT61B* and *UT61C* devices but should also
work with other DMMs supported by *Sigrok*.

Binds to:
  sigrok:
    - `SigrokUSBDevice`_
    - `NetworkSigrokUSBDevice`_
    - `SigrokUSBSerialDevice`_
    - NetworkSigrokUSBSerialDevice

Implements:
  - None yet

Arguments:
  - None

Sampling can be started calling ``capture(samples, timeout=None)``.
It sets up sampling and returns immediately.
The default timeout has been chosen to work with *Unit-T UT61B*.
Other devices may require a different timeout setting.

Samples can be obtained using ``stop()``.
``stop()`` will block until either *sigrok* terminates or *timeout* is reached.
This method returns a ``(unit, samples)`` tuple:
``unit`` is the physical unit reported by the DMM;
samples is an iterable of samples.

This driver relies on buffering of the subprocess call.
Reading a few samples will very likely work - but obtaining a lot of samples may stall.

USBSDMuxDriver
~~~~~~~~~~~~~~
The :any:`USBSDMuxDriver` uses a `USBSDMuxDevice`_ resource to control a
USB-SD-Mux device via `usbsdmux <https://github.com/pengutronix/usbsdmux>`_
tool.

Binds to:
  mux:
    - `USBSDMuxDevice`_
    - `NetworkUSBSDMuxDevice`_

Implements:
  - None yet

Arguments:
  - None

The driver can be used in test cases by calling its ``set_mode()`` method with
argument being "dut", "host", "off", or "client".

LXAUSBMuxDriver
~~~~~~~~~~~~~~~
The :any:`LXAUSBMuxDriver` uses an `LXAUSBMux`_ resource to control a USB-Mux
device via the `usbmuxctl <https://github.com/linux-automation/usbmuxctl>`_
tool.

Binds to:
  mux:
    - `LXAUSBMux`_
    - `NetworkLXAUSBMux`

Implements:
  - None yet

Arguments:
  - None

The driver can be used in test cases by calling its ``set_links()`` method with
a list containing one or more of "dut-device", "host-dut" and "host-device".
Not all combinations can be configured at the same time.

USBSDWireDriver
~~~~~~~~~~~~~~~
The :any:`USBSDWireDriver` uses a `USBSDWireDevice`_ resource to control a
USB-SD-Wire device via `sd-mux-ctrl <https://web.archive.org/web/20220812002642/https://wiki.tizen.org/SD_MUX#Software>`_
tool.

Binds to:
  mux:
    - `USBSDWireDevice`_
    - `NetworkUSBSDWireDevice`

Implements:
  - None yet

Arguments:
  - None

The driver can be used in test cases by calling its ``set_mode()`` method with
argument being "dut", "host", "off", or "client".

USBVideoDriver
~~~~~~~~~~~~~~
The :any:`USBVideoDriver` is used to show a video stream from a remote USB
video camera in a local window.
It uses the GStreamer command line utility ``gst-launch`` on both sides to
stream the video via an SSH connection to the exporter.

Binds to:
  video:
    - `USBVideo`_
    - `NetworkUSBVideo`_

Implements:
  - :any:`VideoProtocol`

Arguments:
  - None

Although the driver can be used from Python code by calling the ``stream()``
method, it is currently mainly useful for the ``video`` subcommand of
``labgrid-client``.
It supports the `Logitech HD Pro Webcam C920` with the USB ID 046d:082d and a
few others.
More cameras can be added to ``get_qualities()`` and ``get_pipeline()`` in
``labgrid/driver/usbvideodriver.py``.
Appropriate configuration parameters can be determined by using the GStreamer
``gst-device-monitor-1.0`` command line utility.

USBAudioInputDriver
~~~~~~~~~~~~~~~~~~~
The :any:`USBAudioInputDriver` is used to receive an audio stream from a local
or remote USB audio input.
It uses the GStreamer command line utility ``gst-launch`` on the sender side to
stream the audio to the client.
For remote resources, this is done via an SSH connection to the exporter.
On the receiver, it either uses ``gst-launch`` for simple playback or
`gst-python <https://gitlab.freedesktop.org/gstreamer/gst-python>`_ for more
complex cases (such as measuring the current volume level).

Binds to:
  res:
    - `USBAudioInput`_
    - `NetworkUSBAudioInput`_

Implements:
  - None yet

Arguments:
  - None

USBTMCDriver
~~~~~~~~~~~~
The :any:`USBTMCDriver` is used to control an oscilloscope via the *USB TMC
protocol*.

Binds to:
  tmc:
    - `USBTMC`_
    - `NetworkUSBTMC`_

Implements:
  - None yet

Arguments:
  - None

Currently, it can be used by the ``labgrid-client`` ``tmc`` subcommands to show
(and save) a screenshot, to show per channel measurements and to execute raw
TMC commands.
It only supports the `Keysight DSO-X 2000` series (with the USB ID 0957:1798),
but more devices can be added by extending ``on_activate()`` in
``labgrid/driver/usbtmcdriver.py`` and writing a corresponding backend in
``labgrid/driver/usbtmc/``.

FlashromDriver
~~~~~~~~~~~~~~
The :any:`FlashromDriver` is used to flash a ROM, using the flashrom utility.

.. code-block:: yaml

   FlashromDriver:
     image: 'foo'

.. code-block:: yaml

   images:
     foo: '../images/image_to_load.raw'

Binds to:
  flashrom_resource:
    - `Flashrom`_
    - `NetworkFlashrom`_

Implements:
  - :any:`BootstrapProtocol`

Arguments:
  - image (str): optional, key in :ref:`images <labgrid-device-config-images>` containing the path
    of an image to bootstrap onto the target

The FlashromDriver allows using the linux util "flashrom" to write directly to a ROM e.g. a NOR SPI
flash. The assumption is that the device flashing the DUT e.g. an exporter is wired to the Flash
to be flashed. The driver implements the bootstrap protocol.
The driver uses tool configuration section and the key: flashrom to determine the path of the
installed flashrom utility.

FlashScriptDriver
~~~~~~~~~~~~~~~~~
The :any:`FlashScriptDriver` is used to run a custom script or program to flash
a device.

.. note::
   This driver is only intended to be used as a last resort when it is
   impossible or impractical to use a different driver.

.. code-block:: yaml

   FlashScriptDriver:
     script: 'foo'
     args:
       - '{device.devnode}'

.. code-block:: yaml

   images:
     foo: '../images/flash_device.sh'

Binds to:
  device:
    - `USBFlashableDevice`_
    - `NetworkUSBFlashableDevice`_

Implements:
  - None (yet)

Arguments:
  - script (str): optional, key in :ref:`images <labgrid-device-config-images>`
    containing the script to execute for writing of the flashable device
  - args (list of str): optional, list of arguments for flash script execution

The FlashScriptDriver allows running arbitrary programs to flash a device.
Some SoC or devices may require custom, one-off, or proprietary programs to
flash.
A target image can be bundled with these programs using a tool like `makeself
<https://makeself.io/>`_,
which can then be executed by labgrid to flash the device using this driver.

Additional arguments may be passed with the ``args`` parameter.
These arguments will be expanded as `Python format strings
<https://docs.python.org/3/library/string.html#format-string-syntax>`_ with the
following keys:

HTTPVideoDriver
~~~~~~~~~~~~~~~
The :any:`HTTPVideoDriver` is used to show a video stream over HTTP or HTTPS
from a remote IP video source in a local window.

Binds to:
  video:
    - `HTTPVideoStream`_

Implements:
  - :any:`VideoProtocol`

Arguments:
  - None

Although the driver can be used from Python code by calling the ``stream()``
method, it is currently mainly useful for the ``video`` subcommand of
``labgrid-client``.

========== =========================================================
Key        Description
========== =========================================================
``device`` The :any:`Resource` bound to the driver
``file``   The :any:`ManagedFile` used to track the flashable script
========== =========================================================

Properties of these keys can be selected using the Python format string syntax,
e.g. ``{device.devnode}`` to select the device node path of a
:any:`USBFlashableDevice`.

DediprogFlashDriver
~~~~~~~~~~~~~~~~~~~
The :any:`DediprogFlashDriver` is used to flash an SPI device using DediprogFlasher dpcmd.

.. code-block:: yaml

   DediprogFlashDriver:
     image: 'foo'

.. code-block:: yaml

   images:
     foo: '../images/image_to_load.raw'

Binds to:
  flasher:
    - `DediprogFlasher`_
    - `NetworkDediprogFlasher`_

Implements:
  - None (yet)

Arguments:
  - image (str): optional, key in :ref:`images <labgrid-device-config-images>` containing the path
    of an image to flash onto the target

The DediprogFlashDriver allows using DediprogFlasher dpcmd to flash or erase SPI
devices. It is assumed that the device flashing is an exporter wired, via a
*Dediprog SF100 SPI NOR Flash Programmer* for instance, to the device being
flashed.

XenaDriver
~~~~~~~~~~
The :any:`XenaDriver` allows to use Xena networking test equipment.
Using the `xenavalkyrie` library a full API to control the tester is available.

Binds to:
  xena_manager:
    - `XenaManager`_

The driver is supposed to work with all Xena products from the "Valkyrie Layer 2-3 Test platform"
Currently tested on a `XenaCompact` chassis equipped with a `1 GE test module`.

DockerDriver
~~~~~~~~~~~~
A :any:`DockerDriver` binds to a `DockerDaemon`_ and is used to create and
control one docker container.

| The driver uses the docker python module to interact with the docker daemon.
| For more information on the parameters see:
| https://docker-py.readthedocs.io/en/stable/containers.html#container-objects

Binds to:
  docker_daemon:
    - `DockerDaemon`_

Implements:
  - :any:`PowerProtocol`

.. code-block:: yaml

   DockerDriver:
     image_uri: 'rastasheep/ubuntu-sshd:16.04'
     pull: 'always'
     container_name: 'ubuntu-lg-example'
     host_config: {'network_mode': 'bridge'}
     network_services: [{'port': 22, 'username': 'root', 'password': 'root'}]

Arguments:
  - image_uri (str): identifier of the docker image to use (may have a tag suffix)
  - pull (str): pull policy, supports "always", "missing", "never". Default is
    "always"

      - always: Always pull the image and throw an error if the pull fails.
      - missing: Pull the image only when the image is not in the local
        containers storage. Throw an error if no image is found and the pull
        fails.
      - never: Never pull the image but use the one from the local containers
        storage. Throw a `docker.errors.ImageNotFound` if no image is found.

  - command (str): optional, command to run in the container (depends on image)
  - volumes (list): optional, list to configure volumes mounted inside the container
  - container_name (str): name of the container
  - environment (list): optional, list of environment variables
  - host_config (dict): dictionary of host configurations
  - network_services (list): dictionaries that describe individual `NetworkService`_
    instances that come alive when the container is created. The "address" argument
    which `NetworkService`_ also requires will be derived automatically upon container
    creation.

LXAIOBusPIODriver
~~~~~~~~~~~~~~~~~
An :any:`LXAIOBusPIODriver` binds to a single `LXAIOBusPIO`_ to toggle and read
the PIO states.

Binds to:
  pio:
    - `LXAIOBusPIO`_
    - `NetworkLXAIOBusPIO`_

.. code-block:: yaml

   LXAIOBusPIODriver: {}

Implements:
  - :any:`DigitalOutputProtocol`

Arguments:
  - None

HttpDigitalOutputDriver
~~~~~~~~~~~~~~~~~~~~~~~
A :any:`HttpDigitalOutputDriver` binds to an `HttpDigitalOutput`_ to set and
get a digital output state via HTTP.

Binds to:
  http:
    - `HttpDigitalOutput`_

.. code-block:: yaml

   HttpDigitalOutputDriver: {}

Implements:
  - :any:`DigitalOutputProtocol`

Arguments:
  - None

PyVISADriver
~~~~~~~~~~~~
The :any:`PyVISADriver` uses a `PyVISADevice`_ resource to control test
equipment manageable by PyVISA.

Binds to:
  pyvisa_resource:
    - `PyVISADevice`_

Implements:
  - None yet

Arguments:
  - None

NetworkInterfaceDriver
~~~~~~~~~~~~~~~~~~~~~~
The :any:`NetworkInterfaceDriver` allows controlling a network interface (such
as Ethernet or WiFi) on the exporter using NetworkManager.

The configuration is based on dictionaries with contents similar to NM's
connection files in INI-format.
Currently basic wired and wireless configuration options have been tested.

To use it, `PyGObject <https://pygobject.readthedocs.io/>`_ must be installed
(on the same system as the network interface).
For Debian, the necessary packages are ``python3-gi`` and ``gir1.2-nm-1.0``.

It supports:

- static and DHCP address configuration
- WiFi client or AP
- connection sharing (DHCP server with NAT)
- listing DHCP leases (if the client has sufficient permissions)

Binds to:
  iface:
    - `NetworkInterface`_
    - `RemoteNetworkInterface`_
    - `USBNetworkInterface`_

Implements:
  - None yet

Arguments:
  - None

RawNetworkInterfaceDriver
~~~~~~~~~~~~~~~~~~~~~~~~~
The :any:`RawNetworkInterfaceDriver` allows "raw" control of a network
interface (such as Ethernet or WiFi).

The labgrid-raw-interface helper (``helpers/labgrid-raw-interface``) needs to
be installed in the PATH and usable via sudo without password.
A configuration file ``/etc/labgrid/helpers.yaml`` must be installed on hosts
exporting network interfaces for the RawNetworkInterfaceDriver, e.g.:

.. code-block:: yaml

   raw-interface:
     denied-interfaces:
       - 'eth1'

It supports:

- recording traffic
- replaying traffic
- basic statistic collection

For now, the RawNetworkInterfaceDriver leaves pre-configuration of the exported
network interface to the user, including:

- disabling DHCP
- disabling IPv6 Duplicate Address Detection (DAD) by SLAAC (Stateless
  Address Autoconfiguration) and Neighbor Discovery
- disabling Generic Receive Offload (GRO)

This might change in the future.

Binds to:
  iface:
    - `NetworkInterface`_
    - `RemoteNetworkInterface`_
    - `USBNetworkInterface`_

Implements:
  - None yet

Arguments:
  - None

.. _conf-strategies:

Strategies
----------
Strategies are used to ensure that the device is in a certain state during a test.
Such a state could be the bootloader or a booted Linux kernel with shell.

BareboxStrategy
~~~~~~~~~~~~~~~
A :any:`BareboxStrategy` has four states:

- unknown
- off
- barebox
- shell

Here is an example environment config:

.. code-block:: yaml
   :name: barebox-env.yaml

   targets:
     main:
       resources:
         RawSerialPort:
           port: '/dev/ttyUSB0'
       drivers:
         ManualPowerDriver: {}
         SerialDriver: {}
         BareboxDriver: {}
         ShellDriver:
           prompt: 'root@[\w-]+:[^ ]+ '
           login_prompt: ' login: '
           username: 'root'
         BareboxStrategy: {}

In order to use the BareboxStrategy via labgrid as a library and transition to
the "shell" state:

.. testsetup:: barebox-strategy

   from labgrid.strategy import BareboxStrategy

   BareboxStrategy.transition = Mock(return_value=None)

.. doctest:: barebox-strategy

   >>> from labgrid import Environment
   >>> e = Environment("barebox-env.yaml")
   >>> t = e.get_target("main")
   >>> s = t.get_driver("BareboxStrategy")
   >>> s.transition("shell")

This command would transition from the bootloader into a Linux shell and
activate the `ShellDriver`_.

ShellStrategy
~~~~~~~~~~~~~
A :any:`ShellStrategy` has three states:

- unknown
- off
- shell

Here is an example environment config:

.. code-block:: yaml
   :name: shell-env.yaml

   targets:
     main:
       resources:
         RawSerialPort:
           port: '/dev/ttyUSB0'
       drivers:
         ManualPowerDriver: {}
         SerialDriver: {}
         ShellDriver:
           prompt: 'root@[\w-]+:[^ ]+ '
           login_prompt: ' login: '
           username: 'root'
         ShellStrategy: {}

In order to use the ShellStrategy via labgrid as a library and transition to
the "shell" state:

.. testsetup:: shell-strategy

   from labgrid.strategy import ShellStrategy

   ShellStrategy.transition = Mock(return_value=None)

.. doctest:: shell-strategy

   >>> from labgrid import Environment
   >>> e = Environment("shell-env.yaml")
   >>> t = e.get_target("main")
   >>> s = t.get_driver("ShellStrategy")

This command would transition directly into a Linux shell and
activate the `ShellDriver`_.

UBootStrategy
~~~~~~~~~~~~~
A :any:`UBootStrategy` has four states:

- unknown
- off
- uboot
- shell

Here is an example environment config:

.. code-block:: yaml
   :name: uboot-env.yaml

   targets:
     main:
       resources:
         RawSerialPort:
           port: '/dev/ttyUSB0'
       drivers:
         ManualPowerDriver: {}
         SerialDriver: {}
         UBootDriver: {}
         ShellDriver:
           prompt: 'root@[\w-]+:[^ ]+ '
           login_prompt: ' login: '
           username: 'root'
         UBootStrategy: {}

In order to use the UBootStrategy via labgrid as a library and transition to
the "shell" state:

.. testsetup:: uboot-strategy

   from labgrid.strategy import UBootStrategy

   UBootStrategy.transition = Mock(return_value=None)

.. doctest:: uboot-strategy

   >>> from labgrid import Environment
   >>> e = Environment("uboot-env.yaml")
   >>> t = e.get_target("main")
   >>> s = t.get_driver("UBootStrategy")
   >>> s.transition("shell")

This command would transition from the bootloader into a Linux shell and
activate the `ShellDriver`_.

DockerStrategy
~~~~~~~~~~~~~~
A :any:`DockerStrategy` has three states:

- unknown
- gone
- accessible

Here is an example environment config:

.. code-block:: yaml
   :name: docker-env.yaml

   targets:
     main:
       resources:
         DockerDaemon:
           docker_daemon_url: 'unix://var/run/docker.sock'
       drivers:
         DockerDriver:
           image_uri: 'rastasheep/ubuntu-sshd:16.04'
           container_name: 'ubuntu-lg-example'
           host_config: {'network_mode': 'bridge'}
           network_services: [{'port': 22, 'username': 'root', 'password': 'root'}]
         DockerStrategy: {}

In order to use the DockerStrategy via labgrid as a library and transition to
the "accessible" state:

.. testsetup:: docker-strategy

   from labgrid.strategy import DockerStrategy

   patch("docker.DockerClient").start()
   DockerStrategy.transition = Mock(return_value=None)

.. doctest:: docker-strategy

   >>> from labgrid import Environment
   >>> e = Environment("docker-env.yaml")
   >>> t = e.get_target("main")
   >>> s = t.get_driver("DockerStrategy")
   >>> s.transition("accessible")

These commands would activate the docker driver which creates and starts
a docker container. This will subsequently make `NetworkService`_ instance(s)
available which can be used for e.g. SSH access.

Reporters
---------

StepReporter
~~~~~~~~~~~~
.. warning::
    The StepReporter is deprecated, use the `StepLogger`_ instead.

The :any:`StepReporter` outputs individual labgrid steps to `STDOUT`.

.. doctest::

    >>> from labgrid import StepReporter
    >>> StepReporter.start()

The Reporter can be stopped with a call to the stop function:

.. doctest::

    >>> from labgrid import StepReporter
    >>> StepReporter.stop()

Stopping the StepReporter if it has not been started will raise an
AssertionError, as will starting an already started StepReporter.

ConsoleLoggingReporter
~~~~~~~~~~~~~~~~~~~~~~
The :any:`ConsoleLoggingReporter` outputs read calls from the console transports into
files. It takes the path as a parameter.

.. doctest::

    >>> from labgrid import ConsoleLoggingReporter
    >>> ConsoleLoggingReporter.start(".")

The Reporter can be stopped with a call to the stop function:

.. doctest::

    >>> from labgrid import ConsoleLoggingReporter
    >>> ConsoleLoggingReporter.stop()

Stopping the ConsoleLoggingReporter if it has not been started will raise an
AssertionError, as will starting an already started StepReporter.

Loggers
-------

StepLogger
~~~~~~~~~~
The :any:`StepLogger` logs individual labgrid steps.

Logging can be set up via ``labgrid.logging.basicConfig()``.

.. doctest::

    >>> import logging
    >>> from labgrid.logging import basicConfig, StepLogger
    >>> basicConfig(level=logging.INFO)
    >>> StepLogger.start()

The logger can be stopped with a call to the stop function:

.. doctest::

    >>> from labgrid.logging import StepLogger
    >>> StepLogger.stop()

Stopping the StepLogger if it has not been started will raise an
AssertionError, as will starting an already started StepLogger.

.. _environment-configuration:

Environment Configuration
-------------------------
The environment configuration for a test environment consists of a YAML file
which contains targets, drivers and resources.

.. note::

  The order is important here:
  Objects are instantiated in the order they appear in the YAML file,
  so if drivers depend on other drivers or resources which are only instantiated later,
  loading the environment will fail.

The skeleton for an environment consists of:

.. code-block:: yaml

   targets:
     <target-1>:
       resources:
         <resource-1>:
           <resource-1 parameters>
         <resource-2>:
           <resource-2 parameters>
       drivers:
         <driver-1>:
           <driver-1 parameters>
         <driver-2>: {} # no parameters for driver-2
       features:
         - <target-feature-1>
     <target-2>:
       resources:
         <resources>
       drivers:
         <drivers>
       options:
         <target-option-1-name>: <value for target-option-1>
         <more target-options>
     <more targets>
   options:
     <option-1 name>: <value for option-1>
     <more options>
   features:
     - <global-feature-1>
   paths:
     <path-1 name>: <absolute or relative path for path-1>
     <more paths>
   images:
     <image-1 name>: <absolute or relative path for image-1>
     <more images>
   tools:
     <tool-1 name>: <absolute or relative path for tool-1>
     <more tools>
   imports:
     - <import.py>
     - <python module>

If you have a single target in your environment, name it "main", as the
``get_target`` function defaults to "main".

All the resources and drivers in this chapter have a YAML example snippet which
can simply be added (at the correct indentation level, one level deeper) to the
environment configuration.

If you want to use multiple drivers of the same type, the resources and drivers
need to be lists, e.g:

.. code-block:: yaml

  resources:
    RawSerialPort:
      port: '/dev/ttyS1'
  drivers:
    SerialDriver: {}

becomes:

.. code-block:: yaml

  resources:
  - RawSerialPort:
      port: '/dev/ttyS1'
  - RawSerialPort:
      port: '/dev/ttyS2'
  drivers:
  - SerialDriver: {}
  - SerialDriver: {}

This configuration doesn't specify which `RawSerialPort`_ to use for each
`SerialDriver`_, so it will cause an exception when instantiating the
:any:`Target`.
To bind the correct driver to the correct resource, explicit ``name`` and
``bindings`` properties are used:

.. code-block:: yaml

  resources:
  - RawSerialPort:
      name: 'foo'
      port: '/dev/ttyS1'
  - RawSerialPort:
      name: 'bar'
      port: '/dev/ttyS2'
  drivers:
  - SerialDriver:
      name: 'foo_driver'
      bindings:
        port: 'foo'
  - SerialDriver:
      name: 'bar_driver'
      bindings:
        port: 'bar'

The property name for the binding (e.g. ``port`` in the example above) is
documented for each individual driver in this chapter.

The YAML configuration file also supports templating for some substitutions,
these are:

- ``LG_*`` variables, are replaced with their respective ``LG_*`` environment
  variable
- ``BASE`` is substituted with the base directory of the YAML file.

As an example:

.. code-block:: yaml

  targets:
    main:
      resources:
        RemotePlace:
          name: !template '$LG_PLACE'
  tools:
    qemu_bin: !template '$BASE/bin/qemu-bin'

would resolve the ``qemu_bin`` path relative to the ``BASE`` dir of the YAML
file and try to use the `RemotePlace`_ with the name set in the ``LG_PLACE``
environment variable.

See the :ref:`labgrid-device-config` man page for documentation on the
top-level ``options``, ``images``, ``tools``, and ``examples`` keys in the
environment configuration.

.. _exporter-configuration:

Exporter Configuration
----------------------
The exporter is configured by using a YAML file (with a syntax similar to the
environment configs used for pytest) or by instantiating the :any:`Environment`
object.
To configure the exporter, you need to define one or more `resource groups`,
each containing one or more `resources`.
The syntax for exported resource names is ``<exporter>/<group>/<class>/<name>``,
which allows the exporter to group resources for various usage scenarios, e.g.
all resources of a specific place or for a specific test setup.
For information on how the exporter fits into the rest of labgrid, see
:any:`remote-resources-and-places`.

The ``<exporter>`` part can be specified on the :ref:`labgrid-exporter` command
line, and defaults to the hostname of the exporter.

The basic structure of an exporter configuration file is:

.. code-block:: yaml

   <group-1>:
     <resource-name-1>:
       <params>
     <resource-name-2>:
       <params>
   <group-2>:
     <resource-name-1>:
       <params>

By default, the class name is inferred from the resource name,
and `<params>` will be passed to its constructor.
For USB resources, you will most likely want to use :ref:`udev-matching` here.

As a simple example, here is one group called ``usb-hub-in-rack12`` containing
a single `USBSerialPort`_ resource (using udev matching), which will be
exported as ``exportername/usb-hub-in-rack12/NetworkSerialPort/USBSerialPort``:

.. code-block:: yaml

   usb-hub-in-rack12:
     USBSerialPort:
       match:
         '@ID_PATH': 'pci-0000:05:00.0-usb-3-1.3'

To export multiple resources of the same class in the same group,
you can choose a unique resource name, and then use the ``cls`` parameter to
specify the class name instead (which will not be passed as a parameter to the
class constructor).
In this next example we will export one `USBSerialPort`_ as
``exportername/usb-hub-in-rack12/NetworkSerialPort/console-main``,
and another `USBSerialPort`_ as
``exportername/usb-hub-in-rack12/NetworkSerialPort/console-secondary``:

.. code-block:: yaml

   usb-hub-in-rack12:
     console-main:
       cls: 'USBSerialPort'
       match:
         '@ID_PATH': 'pci-0000:05:00.0-usb-3-1.3'
     console-secondary:
       cls: 'USBSerialPort'
       match:
         '@ID_PATH': 'pci-0000:05:00.0-usb-3-1.4'

Note that you could also split the resources up into distinct groups instead
to achieve the same effect:

.. code-block:: yaml

   usb-hub-in-rack12-port3:
     USBSerialPort:
       match:
         '@ID_PATH': 'pci-0000:05:00.0-usb-3-1.3'
   usb-hub-in-rack12-port4:
     USBSerialPort:
       match:
         '@ID_PATH': 'pci-0000:05:00.0-usb-3-1.4'

Templating
~~~~~~~~~~
To reduce the amount of repeated declarations when many similar resources
need to be exported, the `Jinja2 template engine <http://jinja.pocoo.org/>`_
is used as a preprocessor for the configuration file:

.. code-block:: yaml

   ## Iterate from group 1001 to 1016
   # for idx in range(1, 17)
   {{ 1000 + idx }}:
     NetworkSerialPort:
       host: 'rl1'
       port: {{ 4000 + idx }}
     NetworkPowerPort:
       # if 1 <= idx <= 8
       model: 'apc'
       host: 'apc1'
       index: {{ idx }}
       # elif 9 <= idx <= 12
       model: 'netio'
       host: 'netio4'
       index: {{ idx - 8 }}
       # elif 13 <= idx <= 16
       model: 'netio'
       host: 'netio5'
       index: {{ idx - 12 }}
       # endif
   # endfor

Use ``#`` for line statements (like the for loops in the example) and ``##``
for line comments.
Statements like ``{{ 4000 + idx }}`` are expanded based on variables in the
Jinja2 template.

The template processing also supports use of OS environment variables, using
something like ``{{ env['FOOBAR'] }}`` to insert the content of environment
variable ``FOOBAR``.
In addition to ``env`` the template also has access to the following variables:

isolated
  ``True`` or ``False``, depending on the :code:`--isolated` command line option.

hostname
  The hostname of the exporter host. Can be used to e.g. construct URLs to the
  current host (``http://{{ hostname }}/``).

name
  The name of the exporter.
