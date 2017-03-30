Configuration
=============
This chapter describes the individual drivers and resources used in a device
configuration.
Drivers can depend on resources or other drivers, resources
have no dependencies.

.. image:: res/config_graph.svg
   :width: 50%

Here the Resource `RawSerialPort` provides the Information for the
`SerialDriver`, which in turn is needed by the `ShellDriver`.
Driver dependency resolution is done by searching for the driver which
implements the dependent protocol, all drivers implement one or more protocols.

Resources
---------

Serial Ports
~~~~~~~~~~~~

RawSerialPort
+++++++++++++
A RawSerialPort is a serial port which is identified via the device path on the
local computer.
Take note that re plugging USB serial converters can result in a different
enumeration order.

.. code-block:: yaml

   RawSerialPort:
     port: /dev/ttyUSB0
     speed: 115200

The example would access the serial port /dev/ttyUSB0 on the local computer with
a baud rate of 115200.

- port (str): path to the serial device
- speed (int): desired baud rate

NetworkSerialPort
+++++++++++++++++
A NetworkSerialPort describes a serial port which is exported over the network,
usually using RFC2217.

.. code-block:: yaml

   NetworkSerialPort:
     host: remote.example.computer
     port: 53867
     speed: 115200

The example would access the serial port on computer remote.example.computer via
port 53867 and use a baud rate of 115200.

- host (str): hostname of the remote host
- port (str): TCP port on the remote host to connect to
- speed (int): baud rate of the serial port

USBSerialPort
+++++++++++++
A USBSerialPort describes a serial port which is connected via USB and is
dentified by matching udev properties.
This allows identification through hot plugging or rebooting.

.. code-block:: yaml

   NetworkSerialPort:
     match:
       ID_SERIAL_SHORT: P-00-00682
     speed: 115200

The example would search for a USB serial converter with the key
`ID_SERIAL_SHORT` and the value `P-00-00682` and use it with a baud rate
of 115200.

- match (str): key and value for a udev match, see `udev Matching`_
- speed (int): baud rate of the serial port

NetworkPowerPort
~~~~~~~~~~~~~~~~
A NetworkPowerPort describes a remotely switchable power port.

.. code-block:: yaml

   NetworkPowerPort:
     model: gude
     host: powerswitch.example.computer
     index: 0

The example describes port 0 on the remote power switch
`powerswitch.example.computer`, which is a `gude` model.

- model (str): model of the power switch
- host (str): hostname of the power switch 
- index (int): number of the port to switch

NetworkService
~~~~~~~~~~~~~~
A NetworkService describes a remote SSH connection.

.. code-block:: yaml

   NetworkPowerPort:
     address: example.computer
     username: root

The example describes a remote SSH connection to the computer `example.computer`
with the username `root`.

- address (str): hostname of the remote system
- username (str): username used by SSH

OneWirePIO
~~~~~~~~~~
A OneWirePIO describes a onewire programmable I/O pin.

.. code-block:: yaml

   OneWirePIO:
     host: example.computer
     path: /29.7D6913000000/PIO.0

The example describes a `PIO.0` on board `29.7D6913000000` via the onewire
server on `example.computer`.

- host (str): hostname of the remote system running the onewire server
- path (str): path on the server to the programmable I/O pin

USBMassStorage
~~~~~~~~~~~~~~
A USBMassStorage resource describes an USB stick.

.. code-block:: yaml

   USBMassStorage:
     match:
       'ID_PATH': 'pci-0000:06:00.0-usb-0:1.3.2:1.0-scsi-0:0:0:3'

- match (str): key and value for a udev match, see `udev Matching`_

IMXUSBLoader
~~~~~~~~~~~~
An IMXUSBLoader resource describes a USB device in the imx loader state.

.. code-block:: yaml

   IMXUSBLoader:
     match:
       'ID_PATH': 'pci-0000:06:00.0-usb-0:1.3.2:1.0'

- match (str): key and value for a udev match, see `udev Matching`_

MXSUSBLoader
~~~~~~~~~~~~
An MXSUSBLoader resource describes a USB device in the mxs loader state.

.. code-block:: yaml

   MXSUSBLoader:
     match:
       'ID_PATH': 'pci-0000:06:00.0-usb-0:1.3.2:1.0'

- match (str): key and value for a udev match, see `udev Matching`_

AndroidFastboot
~~~~~~~~~~~~~~~
An AndroidFastboot resource describes a USB device in the fastboot state.

.. code-block:: yaml

   AndroidFastboot:
     match:
       'ID_PATH': 'pci-0000:06:00.0-usb-0:1.3.2:1.0'

- match (str): key and value for a udev match, see `udev Matching`_

USBEthernetInterface
~~~~~~~~~~~~~~~~~~~~
An USBEthernetInterface resource describes a USB device Ethernet adapter.

.. code-block:: yaml

   USBEthernetInterface:
     match:
       'ID_PATH': 'pci-0000:06:00.0-usb-0:1.3.2:1.0'

- match (str): key and value for a udev match, see `udev Matching`_

AlteraUSBBlaster
~~~~~~~~~~~~~~~~
An AlteraUSBBlaster resource describes an Altera USB blaster.

.. code-block:: yaml

   AlteraUSBBlaster:
     match:
       'ID_PATH': 'pci-0000:06:00.0-usb-0:1.3.2:1.0'

- match (str): key and value for a udev match, see `udev Matching`_

RemotePlace
~~~~~~~~~~~
A RemotePlace describes a set of resources attached to a labgrid remote place.

.. code-block:: yaml

   RemotePlace:
     name: example-place

The example describes the remote place `example-place`. It will connect to the
labgrid remote coordinator, wait until the resources become available and expose
them to the internal environment. 

- name (str): name or pattern of the remote place

udev Matching
~~~~~~~~~~~~~
udev matching allows labgrid to identify resources via their udev properties.
Any udev property key and value can be used, path matching USB devices is
allowed as well.
This allows exporting a specific USB hub port or the correct identification of
a USB serial converter across computers.

The initial matching and monitoring for udev events is handled by the
:any:`UdevManager` class.
This manager is automatically created when a resource derived from
:any:`USBResource` (such as :any:`USBSerialPort`, :any:`IMXUSBLoader` or
:any:`AndroidFastboot`) is instantiated.

To identify the kernel device which corresponds to a configured `USBResource`,
the each existing (and subsequently added) kernel device is matched against the
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
--property``, elements of the ``ATTR(S){}`` dictionary (as shown by ``udevadmin
info <device> -a``) are useable as match keys.
Finally ``sys_name`` allows matching against the name of the directory in
sysfs.
All match entries must succeed for the device to be accepted.

The following examples show how to use the udev matches for some common
use-cases.

Matching a USB Serial Converter on a Hub Port
+++++++++++++++++++++++++++++++++++++++++++++

This will match any USB serial converter connected below the hub port 1.2.5.5
on bus 1.
The `sys_name` value corresponds to the hierarchy of buses and ports as shown
with ``lsusb -t`` and is also usually displayed in the kernel log messages when
new devices are detected.

.. code-block:: yaml

  USBSerialPort:
    match:
      '@sys_name': '1-1.2.5.5'

Note the ``@`` in the ``@sys_name`` match, which applies this match to the
device's parents instead of directly to itself.
This is necessary for the `USBSerialPort` because we actually want to find the
``ttyUSB?`` device below the USB serial converter device.

Matching an Android Fastboot Device
+++++++++++++++++++++++++++++++++++

In this case, we want to match the USB device on that port directly, so we
don't use a parent match.

.. code-block:: yaml

  AndroidFastboot:
    match:
      'sys_name': '1-1.2.3'

Matching a Specific UART in a Dual-Port Adapter
+++++++++++++++++++++++++++++++++++++++++++++++

On this board, the serial console is connected to the second port of an
on-board dual-port USB-UART.
The board itself is connected to the bus 3 and port path 10.2.2.2.
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
      '@sys_name': '3-10.2.2.2'
      'ID_USB_INTERFACE_NUM': '01'

Matching a USB UART by Serial Number
++++++++++++++++++++++++++++++++++++

Most of the USB serial converters in our lab have been programmed with unique
serial numbers.
This makes it easy to always match the same one even if the USB topology
changes or a board is moved between host systems.

.. code-block:: yaml

  USBSerialPort:
    match:
      'ID_SERIAL_SHORT': 'P-00-00679'

To check if your device has a serial number, you can use ``udevadm info``:

.. code-block:: bash

  $ udevadm info /dev/ttyUSB5 | grep SERIAL_SHORT
  E: ID_SERIAL_SHORT=P-00-00679

Drivers
-------

SerialDriver
~~~~~~~~~~~~
A SerialDriver connects to a serial port. It requires one of the serial port
resources.

Binds to:
  - :any:`NetworkSerialPort`
  - :any:`RawSerialPort`
  - :any:`USBSerialPort`

.. code-block:: yaml

   SerialDriver: {}

Implements:
  - :any:`ConsoleProtocol`

Arguments:
  - None

ShellDriver
~~~~~~~~~~~
A ShellDriver binds on top of a `ConsoleProtocol` and is designed to interact
with a login prompt and a Linux shell.

Binds to:
  - :any:`ConsoleProtocol`

Implements:
  - :any:`CommandProtocol`

.. code-block:: yaml

   ShellDriver:
     prompt: 'root@\w+:[^ ]+ '
     login_prompt: ' login: '
     username: 'root'

Arguments:
  - prompt (regex): prompt to match after logging in 
  - login_prompt (regex): match for the login prompt
  - username (str): username to use during login
  - password (str): password to use during login
  - keyfile (str): optional keyfile to upload after login, making the
    :any:`SSHDriver` usable

SSHDriver
~~~~~~~~~
A SSHDriver requires a `NetworkService` resource and allows the execution of
commands and file upload via network.

Binds to:
  - :any:`NetworkService`

Implements:
  - :any:`CommandProtocol`
  - :any:`FileTransferProtocol`

.. code-block:: yaml

   SSHDriver:
     keyfile: example.key

Arguments:
  - keyfile (str): private key to login into the remote system

InfoDriver
~~~~~~~~~~
An InfoDriver provides an interface to retrieve system settings and state. It
requires a `CommandProtocol`.

Binds to:
  - :any:`CommandProtocol`

Implements:
  - :any:`InfoProtocol`

.. code-block:: yaml

   InfoDriver: {}

Arguments:
  - None

UBootDriver
~~~~~~~~~~~
An UBootDriver interfaces with a u-boot boot loader via a `ConsoleProtocol`.

Binds to:
  - :any:`ConsoleProtocol`

Implements:
  - :any:`CommandProtocol`

.. code-block:: yaml

   UBootDriver:
     prompt: 'Uboot> '

Arguments:
  - prompt (regex): u-boot prompt to match
  - password (str): optional u-boot unlock password
  - init_commands (tuple): tuple of commands to execute after matching the
    prompt 

BareboxDriver
~~~~~~~~~~~~~

An BareboxDriver interfaces with a barebox bootloader via a `ConsoleProtocol`.

Binds to:
  - :any:`ConsoleProtocol`

Implements:
  - :any:`CommandProtocol`

.. code-block:: yaml

   BareboxDriver:
     prompt: 'barebox@[^:]+:[^ ]+ '

Arguments:
  - prompt (regex): barebox prompt to match

ExternalConsoleDriver
~~~~~~~~~~~~~~~~~~~~~
An ExternalConsoleDriver implements the `ConsoleProtocol` on top of a command
executed on the local computer.

Implements:
  - :any:`ConsoleProtocol`

.. code-block:: yaml

   ExternalConsoleDriver:
     cmd: 'microcom /dev/ttyUSB2'

Arguments:
  - cmd (str): command to execute and then bind to.

AndroidFastbootDriver
~~~~~~~~~~~~~~~~~~~~~
An AndroidFastbootDriver allows the upload of images to a device in the USB
fastboot state.

Implements:
  - None (yet)

.. code-block:: yaml

   AndroidFastbootDriver:
     image: mylocal.image

Arguments:
  - image (str): image to upload to the device

OpenOCDDriver
~~~~~~~~~~~~~
An OpenOCDDriver controls OpenOCD to bootstrap a target with a bootloader.

Implements:
  - :any:`BootstrapProtocol`

Arguments:
  - config (str): OpenOCD configuration file
  - search (str): include search path for scripts
  - image (str): image to bootstrap onto the device
    
ManualPowerDriver
~~~~~~~~~~~~~~~~~
A ManualPowerDriver requires the user to control the target power states. This
is required if a strategy is used with the target, but no automatic power
control is available.

Implements:
  - :any:`PowerProtocol`

.. code-block:: yaml

   ManualPowerDriver:
     name: 'example-board'

Arguments:
  - name (str): name of the Driver (will be displayed during interaction)

ExternalPowerDriver
~~~~~~~~~~~~~~~~~~~
An ExternalPowerDriver is used to control a targets power state via an external command.

Implements:
  - :any:`PowerProtocol`

.. code-block:: yaml

   ExternalPowerDriver:
     cmd_on: example_command on
     cmd_off: example_command off
     cmd_cycle: example_command cycle

Arguments:
  - cmd_on (str): command to turn power to the board on
  - cmd_off (str): command to turn power to the board off
  - cycle (str): optional command to switch the board off and on
  - delay (float): configurable delay between off and on if cycle is not set

NetworkPowerDriver
~~~~~~~~~~~~~~~~~~
A NetworkPowerDriver controls a `NetworkPowerPort`, allowing control of the
targets power state without user interaction.

Binds to:
  - :any:`NetworkPowerPort`

Implements:
  - :any:`PowerProtocol`

.. code-block:: yaml

   NetworkPowerDriver:
     delay: 5.0

Arguments:
  - delay (float): optional delay between off and on

DigitalOutputPowerDriver
~~~~~~~~~~~~~~~~~~~~~~~~
A DigitalOutputPowerDriver can be used to control a device with external
commands and a digital output port. The digital output port is used to reset the
device.

Binds to:
  - :any:`DigitalOutputProtocol`

.. code-block:: yaml

   DigitalOutputPowerDriver:
     cmd_on: example_command on
     cmd_off: example_command off

Arguments:
  - cmd_on (str): command to turn power to the board on
  - cmd_off (str): command to turn power to the board off
  - delay (float): configurable delay between off and on if cycle is not set

MXSUSBDriver
~~~~~~~~~~~~
A MXUSBDriver is used to upload an image into a device in the mxs USB loader
state. This is useful to bootstrap a bootloader onto a device.

Binds to:
  - :any:`MXSUSBLoader`
  - :any:`NetworkMXSUSBLoader`

Implements:
  - :any:`BootstrapProtocol`

.. code-block:: yaml

   MXSUSBDriver:
     image: mybootloader.img

Arguments:
  - image (str): The image to bootstrap onto the target

IMXUSBDriver
~~~~~~~~~~~~
A IMXUSBDriver is used to upload an image into a device in the mxs USB loader
state. This is useful to bootstrap a bootloader onto a device.

Binds to:
  - :any:`IMXUSBLoader`
  - :any:`NetworkIMXUSBLoader`

Implements:
  - :any:`BootstrapProtocol`

.. code-block:: yaml

   IMXUSBDriver:
     image: mybootloader.img


Arguments:
  - image (str): The image to bootstrap onto the target

USBStorageDriver
~~~~~~~~~~~~~~~~
An USBStorageDriver allows access to a USB Stick via the `USBMassStorage`
resource.

Binds to:
  - :any:`USBMassStorage`

Implements:
  - None (yet)

.. code-block:: yaml

   USBStorageDriver: {}


Arguments:
  - None

Strategies
~~~~~~~~~~

Environment Configuration
-------------------------

Exporter Configuration
----------------------

