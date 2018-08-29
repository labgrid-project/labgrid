Configuration
=============
This chapter describes the individual drivers and resources used in a device
configuration.
Drivers can depend on resources or other drivers, whereas resources
have no dependencies.

.. image:: res/config_graph.svg
   :width: 50%

Here the resource `RawSerialPort` provides the information for the
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
Take note that re-plugging USB serial converters can result in a different
enumeration order.

.. code-block:: yaml

   RawSerialPort:
     port: /dev/ttyUSB0
     speed: 115200

The example would access the serial port /dev/ttyUSB0 on the local computer with
a baud rate of 115200.

- port (str): path to the serial device
- speed (int): desired baud rate

Used by:
  - `SerialDriver`_

NetworkSerialPort
+++++++++++++++++
A NetworkSerialPort describes a serial port which is exported over the network,
usually using RFC2217 or raw tcp.

.. code-block:: yaml

   NetworkSerialPort:
     host: remote.example.computer
     port: 53867
     speed: 115200

The example would access the serial port on computer remote.example.computer via
port 53867 and use a baud rate of 115200 with the RFC2217 protocol.

- host (str): hostname of the remote host
- port (str): TCP port on the remote host to connect to
- speed (int): baud rate of the serial port
- protocol (str): optional, protocol used for connection: raw or rfc2217

Used by:
  - `SerialDriver`_

USBSerialPort
+++++++++++++
A USBSerialPort describes a serial port which is connected via USB and is
identified by matching udev properties.
This allows identification through hot-plugging or rebooting.

.. code-block:: yaml

   USBSerialPort:
     match:
       'ID_SERIAL_SHORT': 'P-00-00682'
     speed: 115200

The example would search for a USB serial converter with the key
`ID_SERIAL_SHORT` and the value `P-00-00682` and use it with a baud rate
of 115200.

- match (str): key and value for a udev match, see `udev Matching`_
- speed (int): baud rate of the serial port

Used by:
  - `SerialDriver`_

Power Ports
~~~~~~~~~~~

NetworkPowerPort
++++++++++++++++
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

Used by:
  - `NetworkPowerDriver`_

YKUSHPowerPort
++++++++++++++
A YKUSHPowerPort describes a YEPKIT YKUSH USB (HID) switchable USB hub.

.. code-block:: yaml

   YKUSHPowerPort:
     serial: YK12345
     index: 1

The example describes port 1 on the YKUSH USB hub with the
serial "YK12345".
(use "pykush -l" to get your serial...)

- serial (str): serial number of the YKUSH hub
- index (int): number of the port to switch

Used by:
  - `YKUSHPowerDriver`_

USBPowerPort
++++++++++++
A USBPowerPort describes a generic switchable USB hub as supported by
`uhubctl <https://github.com/mvp/uhubctl>`_.

.. code-block:: yaml

   USBPowerPort:
     match:
       ID_PATH: pci-0000:00:14.0-usb-0:2:1.0
     index: 1

The example describes port 1 on the hub with the ID_PATH
"pci-0000:00:14.0-usb-0:2:1.0".
(use "udevadmin info /sys/bus/usb/devices/..." to find the ID_PATH value)

- index (int): number of the port to switch

Used by:
  - `USBPowerDriver`_

ModbusTCPCoil
~~~~~~~~~~~~~
A ModbusTCPCoil describes a coil accessible via ModbusTCP.

.. code-block:: yaml

   ModbusTCPCoil:
     host: "192.168.23.42"
     coil: 1

The example describes the coil with the address 1 on the ModbusTCP device
`192.168.23.42`.

- host (str): hostname of the Modbus TCP server e.g. "192.168.23.42:502"
- coil (int): index of the coil e.g. 3
- invert (bool): optional, whether the logic level is be inverted (active-low)

Used by:
  - `ModbusCoilDriver`_

NetworkService
~~~~~~~~~~~~~~
A NetworkService describes a remote SSH connection.

.. code-block:: yaml

   NetworkService:
     address: example.computer
     username: root

The example describes a remote SSH connection to the computer `example.computer`
with the username `root`.
Set the optional password password property to make SSH login with a password
instead of the key file (needs sshpass to be installed)

- address (str): hostname of the remote system
- username (str): username used by SSH
- password (str): password used by SSH
- port (int): optional, port used by SSH (default 22)

Used by:
  - `SSHDriver`_

OneWirePIO
~~~~~~~~~~
A OneWirePIO describes a onewire programmable I/O pin.

.. code-block:: yaml

   OneWirePIO:
     host: example.computer
     path: /29.7D6913000000/PIO.0
     invert: false

The example describes a `PIO.0` at device address `29.7D6913000000` via the onewire
server on `example.computer`.

- host (str): hostname of the remote system running the onewire server
- path (str): path on the server to the programmable I/O pin
- invert (bool): optional, whether the logic level is be inverted (active-low)

Used by:
  - `OneWirePIODriver`_

USBMassStorage
~~~~~~~~~~~~~~
A USBMassStorage resource describes a USB memory stick or similar device.

.. code-block:: yaml

   USBMassStorage:
     match:
       'ID_PATH': 'pci-0000:06:00.0-usb-0:1.3.2:1.0-scsi-0:0:0:3'

- match (str): key and value for a udev match, see `udev Matching`_

Used by:
  - `USBStorageDriver`_
  - `NetworkUSBStorageDriver`_

NetworkUSBMassStorage
~~~~~~~~~~~~~~~~~~~~~
A NetworkUSBMassStorage resource describes a USB memory stick or similar
device available on a remote computer.

Used by:
  - `NetworkUSBStorageDriver`_

The NetworkUSBMassStorage can be used in test cases by calling the
`write_image()`, and `get_size()` functions.

SigrokDevice
~~~~~~~~~~~~
A SigrokDevice resource describes a sigrok device. To select a specific device
from all connected supported devices use the `SigrokUSBDevice`_.

.. code-block:: yaml

   SigrokUSBDevice:
     driver: fx2lafw
     channel: "D0=CLK,D1=DATA"

- driver (str): name of the sigrok driver to use
- channel (str): channel mapping as described in the sigrok-cli man page

Used by:
  - `SigrokDriver`_

IMXUSBLoader
~~~~~~~~~~~~
An IMXUSBLoader resource describes a USB device in the imx loader state.

.. code-block:: yaml

   IMXUSBLoader:
     match:
       'ID_PATH': 'pci-0000:06:00.0-usb-0:1.3.2:1.0'

- match (str): key and value for a udev match, see `udev Matching`_

Used by:
  - `IMXUSBDriver`_

MXSUSBLoader
~~~~~~~~~~~~
An MXSUSBLoader resource describes a USB device in the mxs loader state.

.. code-block:: yaml

   MXSUSBLoader:
     match:
       'ID_PATH': 'pci-0000:06:00.0-usb-0:1.3.2:1.0'

- match (str): key and value for a udev match, see `udev Matching`_

Used by:
  - `MXSUSBDriver`_

NetworkMXSUSBLoader
~~~~~~~~~~~~~~~~~~~
A NetworkMXSUSBLoader descibes an `MXSUSBLoader`_ available on a remote computer.

NetworkIMXUSBLoader
~~~~~~~~~~~~~~~~~~~
A NetworkIMXUSBLoader descibes an `IMXUSBLoader`_ available on a remote computer.

AndroidFastboot
~~~~~~~~~~~~~~~
An AndroidFastboot resource describes a USB device in the fastboot state.

.. code-block:: yaml

   AndroidFastboot:
     match:
       'ID_PATH': 'pci-0000:06:00.0-usb-0:1.3.2:1.0'

- match (str): key and value for a udev match, see `udev Matching`_

Used by:
  - `AndroidFastbootDriver`_

USBEthernetInterface
~~~~~~~~~~~~~~~~~~~~
A USBEthernetInterface resource describes a USB device Ethernet adapter.

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

- match (dict): key and value for a udev match, see `udev Matching`_

Used by:
  - `OpenOCDDriver`_
  - `QuartusHPSDriver`_

SNMPEthernetPort
~~~~~~~~~~~~~~~~
A SNMPEthernetPort resource describes a port on an Ethernet switch, which is
accessible via SNMP.

.. code-block:: yaml

   SNMPEthernetPort:
     switch: "switch-012"
     interface: "17"

- switch (str): host name of the Ethernet switch
- interface (str): interface name

SigrokUSBDevice
~~~~~~~~~~~~~~~~
A SigrokUSBDevice resource describes a sigrok USB device.

.. code-block:: yaml

   SigrokUSBDevice:
     driver: fx2lafw
     channel: "D0=CLK,D1=DATA"
     match:
       'ID_PATH': 'pci-0000:06:00.0-usb-0:1.3.2:1.0'

- driver (str): name of the sigrok driver to use
- channel (str): channel mapping as described in the sigrok-cli man page
- match (str): key and value for a udev match, see `udev Matching`_

Used by:
  - `SigrokDriver`_

NetworkSigrokUSBDevice
~~~~~~~~~~~~~~~~~~~~~~
A NetworkSigrokUSBDevice resource describes a sigrok USB device connected to a
host which is exported over the network. The SigrokDriver will access it via SSH.

.. code-block:: yaml

   NetworkSigrokUSBDevice:
     driver: fx2lafw
     channel: "D0=CLK,D1=DATA"
     match:
       'ID_PATH': 'pci-0000:06:00.0-usb-0:1.3.2:1.0'
     host: remote.example.computer

- driver (str): name of the sigrok driver to use
- channel (str): channel mapping as described in the sigrok-cli man page
- match (str): key and value for a udev match, see `udev Matching`_

Used by:
  - `SigrokDriver`_

USBSDMuxDevice
~~~~~~~~~~~~~~
A :any:`USBSDMuxDevice` resource describes a Pengutronix
`USB-SD-Mux <https://www.pengutronix.de/de/2017-10-23-usb-sd-mux-automated-sd-card-juggler.html>`_
device.

.. code-block:: yaml

   USBSDMuxDevice:
     match:
       '@ID_PATH': 'pci-0000:00:14.0-usb-0:1.2'

- match (str): key and value for a udev match, see `udev Matching`_

Used by:
  - `USBSDMUXDriver`_

NetworkUSBSDMuxDevice
~~~~~~~~~~~~~~~~~~~~~

A :any:`NetworkUSBSDMuxDevice` resource describes a `USBSDMuxDevice`_ available
on a remote computer.

USBVideo
~~~~~~~~

A :any:`USBVideo` resource describes a USB video camera which is supported by a
Video4Linux2 kernel driver.

.. code-block:: yaml

   USBVideo:
     match:
       '@ID_PATH': 'pci-0000:00:14.0-usb-0:1.2'

Used by:
  - `USBVideoDriver`_

NetworkUSBVideo
~~~~~~~~~~~~~~~

A :any:`NetworkUSBVideo` resource describes a :any:`USBVideo` resource available
on a remote computer.

USBTMC
~~~~~~

A :any:`USBTMC` resource describes an oscilloscope connected via the USB TMC
protocol.
The low-level communication is handled by the ``usbtmc`` kernel driver.


.. code-block:: yaml

   USBTMC:
     match:
       '@ID_PATH': 'pci-0000:00:14.0-usb-0:1.2'

A udev rules file may be needed to allow access for non-root users:

.. code-block:: none

   DRIVERS=="usbtmc", MODE="0660", GROUP="plugdev"

Used by:
  - `USBTMCDriver`_

NetworkUSBTMC
~~~~~~~~~~~~~

A :any:`NetworkUSBTMC` resource describes a :any:`USBTMC` resource available
on a remote computer.

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

Used by:
  - potentially all drivers

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
changes or a board has been moved between host systems.

.. code-block:: yaml

  USBSerialPort:
    match:
      'ID_SERIAL_SHORT': 'P-00-00679'

To check if your device has a serial number, you can use ``udevadm info``:

.. code-block:: bash

  $ udevadm info /dev/ttyUSB5 | grep SERIAL_SHORT
  E: ID_SERIAL_SHORT=P-00-00679

DockerNetworkService
~~~~~~~~~~~~~~~~~~~~
A DockerNetworkService describes a network service served from a docker 
container.

.. code-block:: yaml

   DockerNetworkService:
     container_name: example_container
     username: root

The example describes a remote SSH connection to the docker container running 
with the name `example_container` using the username `root`.

- container_name (str): the name of the docker container the service is served 
                        from
- username (str): username used by SSH
- password (str): password used by SSH
- port (int): optional, port used by SSH (default 22)

Used by:
  - `SSHDriver`_

DockerDaemon
~~~~~~~~~~~~
A DockerDaemon describes the location of a docker daemon.

.. code-block:: yaml

   DockerDaemon:
     docker_daemon_url: 'unix://var/run/docker.sock'

The example describes a docker daemon accessible via the '/var/run/docker.sock'
unix socket.

- docker_daemon_url (str): The url of the daemon to use for this target.

Used by:
  - `DockerNetworkService`_
  - `DockerDriver`_

Drivers
-------

DockerDriver
~~~~~~~~~~~~
A DockerDriver connects to a DockerDaemon and is used to create and control one
docker container.

The driver uses the Docker SDK for python to interact with the docker daemon.
For more information on the parameters see
https://docker-py.readthedocs.io/en/3.3.0/api.html#module-docker.api.container

Binds to:
  port:
    - `DockerDaemon`_

.. code-block:: yaml

   DockerDriver:
     image_uri: "rastasheep/ubuntu-sshd:16.04"
     container_name: "ubuntu-lg-example"
     host_config: {"network_mode":"bridge"}

Arguments:
  - image_uri (str): uri of a docker image and tag
  - command (str): the command to run in the container
  - volumes (list): a list to configure volumes mounted inside the container
  - container_name (str): the name of the container
  - entry_point (str): the entrypoint for the container
  - environment (list): a list of environment variables
  - host_config (dict): a dictionary of host configurations

SerialDriver
~~~~~~~~~~~~
A SerialDriver connects to a serial port. It requires one of the serial port
resources.

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

Arguments:
  - txdelay (float): time in seconds to wait before sending each byte

ShellDriver
~~~~~~~~~~~
A ShellDriver binds on top of a `ConsoleProtocol` and is designed to interact
with a login prompt and a Linux shell.

Binds to:
  console:
    - :any:`ConsoleProtocol`

Implements:
  - :any:`CommandProtocol`

.. code-block:: yaml

   ShellDriver:
     prompt: 'root@\w+:[^ ]+ '
     login_prompt: ' login: '
     username: 'root'

Arguments:
  - prompt (regex): shell prompt to match after logging in
  - login_prompt (regex): match for the login prompt
  - username (str): username to use during login
  - password (str): password to use during login
  - keyfile (str): optional keyfile to upload after login, making the
    `SSHDriver`_ usable
  - login_timeout (int): optional, timeout for login prompt detection in
    seconds (default 60)
  - await_login_timeout (int): optional, time in seconds of silence that needs
    to pass before sending a newline to device.
  - console_ready (regex): optional, pattern used by the kernel to inform
    the user that a console can be activated by pressing enter.

.. _conf-sshdriver:

SSHDriver
~~~~~~~~~
A SSHDriver requires a `NetworkService` resource and allows the execution of
commands and file upload via network.

Binds to:
  networkservice:
    - `NetworkService`_

Implements:
  - :any:`CommandProtocol`
  - :any:`FileTransferProtocol`

.. code-block:: yaml

   SSHDriver:
     keyfile: example.key

Arguments:
  - keyfile (str): filename of private key to login into the remote system
    (only used if password is not set)

InfoDriver
~~~~~~~~~~
An InfoDriver provides an interface to retrieve system settings and state. It
requires a `CommandProtocol`.

Binds to:
  command:
    - :any:`CommandProtocol`

Implements:
  - :any:`InfoProtocol`

.. code-block:: yaml

   InfoDriver: {}

Arguments:
  - None

UBootDriver
~~~~~~~~~~~
A UBootDriver interfaces with a u-boot boot loader via a `ConsoleProtocol`.

Binds to:
  console:
    - :any:`ConsoleProtocol`

Implements:
  - :any:`CommandProtocol`

.. code-block:: yaml

   UBootDriver:
     prompt: 'Uboot> '

Arguments:
  - prompt (regex): u-boot prompt to match
  - password (str): optional, u-boot unlock password
  - interrupt (str, default="\\n"): string to interrupt autoboot (use "\\x03" for CTRL-C)
  - init_commands (tuple): tuple of commands to execute after matching the
    prompt
  - password_prompt (str): optional, regex to match the uboot password prompt,
    defaults to "enter Password: "
  - boot_expression (str): optional, regex to match the uboot start string
    defaults to "U-Boot 20\d+"
  - bootstring (str): optional, regex to match on Linux Kernel boot
  - login_timeout (int): optional, timeout for login prompt detection in
    seconds (default 60)

SmallUBootDriver
~~~~~~~~~~~~~~~~
A SmallUBootDriver interfaces with stripped-down UBoot variants that are
sometimes used in cheap consumer electronics.

SmallUBootDriver is meant as a driver for UBoot with only little
functionality compared to standard a standard UBoot.
Especially is copes with the following limitations:

- The UBoot does not have a real password-prompt but can be activated by
  entering a "secret" after a message was displayed.
- The command line is does not have a build-in echo command. Thus this
  driver uses 'Unknown Command' messages as marker before and after the
  output of a command.
- Since there is no echo we can not return the exit code of the command.
  Commands will always return 0 unless the command was not found.

This driver needs the following features activated in UBoot to work:

- The UBoot must not have real password prompt. Instead it must be
  keyword activated.
  For example it should be activated by a dialog like the following:

  - UBoot: "Autobooting in 1s..."
  - Labgrid: "secret"
  - UBoot: <switching to console>

- The UBoot must be able to parse multiple commands in a single
  line separated by ";".
- The UBoot must support the "bootm" command to boot from a
  memory location.

Binds to:
  - :any:`ConsoleProtocol` (see `SerialDriver`_)

Implements:
  - :any:`CommandProtocol`

.. code-block:: yaml

   SmallUBootDriver:
     prompt: 'ap143-2\.0> '
     boot_expression: 'Autobooting in 1 seconds'
     boot_secret: "tpl"

Arguments:
  - prompt (regex): u-boot prompt to match
  - init_commands (tuple): tuple of commands to execute after matching the
    prompt
  - boot_expression (str): optional, regex to match the uboot start string
    defaults to "U-Boot 20\d+"

BareboxDriver
~~~~~~~~~~~~~

A BareboxDriver interfaces with a barebox bootloader via a `ConsoleProtocol`.

Binds to:
  console:
    - :any:`ConsoleProtocol`

Implements:
  - :any:`CommandProtocol`

.. code-block:: yaml

   BareboxDriver:
     prompt: 'barebox@[^:]+:[^ ]+ '

Arguments:
  - prompt (regex): barebox prompt to match
  - autoboot (regex, default="stop autoboot"): autoboot message to match
  - interrupt (str, default="\\n"): string to interrupt autoboot (use "\\x03" for CTRL-C)
  - startstring (regex, default="[\n]barebox 20\d+"): string that indicates that Barebox is starting
  - bootstring (regex, default="Linux version \d"): succesfully jumped into the kernel 
  - password (str): optional, password to use for access to the shell
  - login_timeout (int): optional, timeout for access to the shell

ExternalConsoleDriver
~~~~~~~~~~~~~~~~~~~~~
An ExternalConsoleDriver implements the `ConsoleProtocol` on top of a command
executed on the local computer.

Implements:
  - :any:`ConsoleProtocol`

.. code-block:: yaml

   ExternalConsoleDriver:
     cmd: 'microcom /dev/ttyUSB2'
     txdelay: 0.05

Arguments:
  - cmd (str): command to execute and then bind to.
  - txdelay (float): time in seconds to wait before sending each byte

AndroidFastbootDriver
~~~~~~~~~~~~~~~~~~~~~
An AndroidFastbootDriver allows the upload of images to a device in the USB
fastboot state.

Binds to:
  fastboot:
    - `AndroidFastboot`_

Implements:
  - None (yet)

.. code-block:: yaml

   AndroidFastbootDriver:
     image: mylocal.image

Arguments:
  - image (str): filename of the image to upload to the device

OpenOCDDriver
~~~~~~~~~~~~~
An OpenOCDDriver controls OpenOCD to bootstrap a target with a bootloader.

Binds to:
  interface:
    - `AlteraUSBBlaster`_

Implements:
  - :any:`BootstrapProtocol`

Arguments:
  - config (str): OpenOCD configuration file
  - search (str): include search path for scripts
  - image (str): filename of image to bootstrap onto the device

QuartusHPSDriver
~~~~~~~~~~~~~~~~
A QuartusHPSDriver controls the "Quartus Prime Programmer and Tools" to flash
a target's QSPI.

Binds to:
  - `AlteraUSBBlaster`_

Implements:
  - None

Arguments:
  - image (str): filename of image to flash QSPI

The driver can be used in test cases by calling the `flash` function. An
example strategy is included in Labgrid.

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
  - name (str): name of the driver (will be displayed during interaction)

ExternalPowerDriver
~~~~~~~~~~~~~~~~~~~
An ExternalPowerDriver is used to control a target power state via an external command.

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
  - delay (float): configurable delay in seconds between off and on if cycle is not set

NetworkPowerDriver
~~~~~~~~~~~~~~~~~~
A NetworkPowerDriver controls a `NetworkPowerPort`, allowing control of the
target power state without user interaction.

Binds to:
  port:
    - `NetworkPowerPort`_

Implements:
  - :any:`PowerProtocol`

.. code-block:: yaml

   NetworkPowerDriver:
     delay: 5.0

Arguments:
  - delay (float): optional delay in seconds between off and on

YKUSHPowerDriver
~~~~~~~~~~~~~~~~
A YKUSHPowerDriver controls a `YKUSHPowerPort`, allowing control of the
target power state without user interaction.

Binds to:
  port:
    - `YKUSHPowerPort`_

Implements:
  - :any:`PowerProtocol`

.. code-block:: yaml

   YKUSHPowerDriver:
     delay: 5.0

Arguments:
  - delay (float): optional delay in seconds between off and on

DigitalOutputPowerDriver
~~~~~~~~~~~~~~~~~~~~~~~~
A DigitalOutputPowerDriver can be used to control the power of a
Device using a DigitalOutputDriver.

Using this driver you probably want an external relay to switch the
power of your DUT.

Binds to:
  output:
    - :any:`DigitalOutputProtocol`

.. code-block:: yaml

   DigitalOutputPowerDriver:
     delay: Delay for a power cycle

Arguments:
  - delay (float): configurable delay in seconds between off and on

USBPowerDriver
~~~~~~~~~~~~~~
A USBPowerDriver controls a `USBPowerPort`, allowing control of the target
power state without user interaction.

Binds to:
  - `USBPowerPort`_

Implements:
  - :any:`PowerProtocol`

.. code-block:: yaml

   USBPowerPort:
     delay: 5.0

Arguments:
  - delay (float): optional delay in seconds between off and on

SerialPortDigitalOutputDriver
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The SerialPortDigitalOutputDriver makes it possible to use a UART
as a 1-Bit general-purpose digital output.

This driver sits on top of a SerialDriver and uses the it's pyserial-
port to control the flow control lines.

Implements:
  - :any:`DigitalOutputProtocol`

.. code-block:: yaml

   SerialPortDigitalOutputDriver:
     signal: "DTR"
     bindings: { serial : "nameOfSerial" }

Arguments:
  - signal (str): control signal to use: DTR or RTS
  - bindings (dict): A named ressource of the type SerialDriver to
    bind against. This is only needed if you have multiple
    SerialDriver in your environment (what is likely to be the case
    if you are using this driver).

ModbusCoilDriver
~~~~~~~~~~~~~~~~
A ModbusCoilDriver controls a `ModbusTCPCoil` resource.
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

MXSUSBDriver
~~~~~~~~~~~~
A MXUSBDriver is used to upload an image into a device in the mxs USB loader
state. This is useful to bootstrap a bootloader onto a device.

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
           image: mybootloaderkey

   images:
     mybootloaderkey: path/to/mybootloader.img

Arguments:
  - image (str): The key in :ref:`images <labgrid-device-config-images>` containing the path of an image to bootstrap onto the target

IMXUSBDriver
~~~~~~~~~~~~
A IMXUSBDriver is used to upload an image into a device in the imx USB loader
state. This is useful to bootstrap a bootloader onto a device.

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
         IMXUSBDriver:
           image: mybootloaderkey

   images:
     mybootloaderkey: path/to/mybootloader.img

Arguments:
  - image (str): The key in :ref:`images <labgrid-device-config-images>` containing the path of an image to bootstrap onto the target

USBStorageDriver
~~~~~~~~~~~~~~~~
A USBStorageDriver allows access to a USB stick or similar device via the `USBMassStorage`
resource.

Binds to:
  storage:
    - `USBMassStorage`_

Implements:
  - None (yet)

.. code-block:: yaml

   USBStorageDriver: {}


Arguments:
  - None

NetworkUSBStorageDriver
~~~~~~~~~~~~~~~~~~~~~~~
A NetworkUSBStorageDriver allows access to a USB stick or similar local or
remote device.

Binds to:
  - `USBMassStorage`_
  - `NetworkUSBMassStorage`_

Implements:
  - None (yet)

.. code-block:: yaml

   NetworkUSBStorageDriver: {}

Arguments:
  - None

OneWirePIODriver
~~~~~~~~~~~~~~~~
A OneWirePIODriver controls a `OneWirePIO` resource.
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

QEMUDriver
~~~~~~~~~~
The QEMUDriver allows the usage of a qemu instance as a target. It requires
several arguments, listed below.
The kernel, flash, rootfs and dtb arguments refer to images and paths declared
in the environment configuration.

Binds to:
  - None

.. code-block:: yaml

   QEMUDriver:
     qemu_bin: qemu_arm
     machine: vexpress-a9
     cpu: cortex-a9
     memory: 512M
     boot_args: "root=/dev/root console=ttyAMA0,115200"
     extra_args: ""
     kernel: kernel
     rootfs: rootfs
     dtb: dtb

.. code-block:: yaml

   tools:
     qemu_arm: /bin/qemu-system-arm
   paths:
     rootfs: ../images/root
   images:
     dtb: ../images/mydtb.dtb
     kernel: ../images/vmlinuz
     

Implements:
  - :any:`ConsoleProtocol`
  - :any:`PowerProtocol`

Arguments:
  - qemu_bin (str): reference to the tools key for the QEMU binary
  - machine (str): QEMU machine type
  - cpu (str): QEMU cpu type
  - memory (str): QEMU memory size (ends with M or G)
  - extra_args (str): extra QEMU arguments, they are passed directly to the QEMU binary
  - boot_args (str): optional, additional kernel boot argument
  - kernel (str): optional, reference to the images key for the kernel
  - disk (str): optional, reference to the images key for the disk image
  - flash (str): optional, reference to the images key for the flash image
  - rootfs (str): optional, reference to the paths key for use as the virtio-9p filesystem
  - dtb (str): optional, reference to the image key for the device tree

The qemudriver also requires the specification of:

- a tool key, this contains the path to the qemu binary 
- an image key, the path to the kernel image and optionally the dtb key to
  specify the build device tree
- a path key, this is the path to the rootfs

SigrokDriver
~~~~~~~~~~~~
The SigrokDriver uses a SigrokDriver Resource to record samples and provides
them during test runs.

Binds to:
  sigrok:
    - `SigrokUSBDevice`_
    - `SigrokDevice`_
    - `NetworkSigrokUSBDevice`_

Implements:
  - None yet

The driver can be used in test cases by calling the `capture`, `stop` and
`analyze` functions.

USBSDMuxDriver
~~~~~~~~~~~~~~
The :any:`USBSDMuxDriver` uses a USBSDMuxDevice resource to control a
USB-SD-Mux device via `usbsdmux <https://github.com/pengutronix/usbsdmux>`_
tool.

Implements:
  - None yet

The driver can be used in test cases by calling the `set_mode()` function with
argument being `dut`, `host`, `off`, or `client`.

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
  - None yet

Although the driver can be used from Python code by calling the `stream()`
method, it is currenly mainly useful for the ``video`` subcommand of
``labgrid-client``.
It supports the `Logitech HD Pro Webcam C920` with the USB ID 046d:082d, but
other cameras can be added to `get_caps()` in
``labgrid/driver/usbvideodriver.py``.

USBTMCDriver
~~~~~~~~~~~~
The :any:`USBTMCDriver` is used to control a oscilloscope via the USB TMC
protocol.

Binds to:
  tmc:
    - `USBTMC`_
    - `NetworkUSBTMC`_

Implements:
  - None yet

Currently, it can be used by the ``labgrid-client`` ``tmc`` subcommands to show
(and save) a screenshot, to show per channel measurements and to execute raw
TMC commands.
It only supports the `Keysight DSO-X 2000` series (with the USB ID 0957:1798),
but more devices can be added by extending `on_activate()` in
``labgrid/driver/usbtmcdriver.py`` and writing a corresponding backend in
``labgrid/driver/usbtmc/``.

Strategies
----------

Strategies are used to ensure that the device is in a certain state during a test. 
Such a state could be the boot loader or a booted Linux kernel with shell.

BareboxStrategy
~~~~~~~~~~~~~~~
A BareboxStrategy has three states:

- unknown
- barebox
- shell


to transition to the shell state:

::

   t = get_target("main")
   s = BareboxStrategy(t)
   s.transition("shell")


this command would transition from the boot loader into a Linux shell and
activate the shelldriver.

ShellStrategy
~~~~~~~~~~~~~
A ShellStrategy has three states:

- unknown
- off
- shell


to transition to the shell state:

::

   t = get_target("main")
   s = ShellStrategy(t)
   s.transition("shell")


this command would transition directly into a Linux shell and
activate the shelldriver.

UBootStrategy
~~~~~~~~~~~~~
A UBootStrategy has three states:

- unknown
- uboot
- shell


to transition to the shell state:

::

   t = get_target("main")
   s = UBootStrategy(t)
   s.transition("shell")


this command would transition from the boot loader into a Linux shell and
activate the shelldriver.

DockerShellStrategy
~~~~~~~~~~~~~~~~~~~
A DockerShellStrategy has three states:

- unknown
- off
- shell


to transition to the shell state:

::

   t = get_target("main")
   s = ShellStrategy(t)
   s.transition("shell")


these commands would activate the docker driver which creates a docker container,
and start the container which could make it available for sshaccess etc.

Reporters
---------

StepReporter
~~~~~~~~~~~~
The StepReporter outputs individual labgrid steps to `STDOUT`.

::

    from labgrid.stepreporter import StepReporter

    StepReporter.start()

The Reporter can be stopped with a call to the stop function:

::

    from labgrid.stepreporter import StepReporter

    StepReporter.stop()

Stopping the StepReporter if it has not been started will raise an
AssertionError, as will starting an already started StepReporter.

ConsoleLoggingReporter
~~~~~~~~~~~~~~~~~~~~~~
The ConsoleLoggingReporter outputs read calls from the console transports into
files. It takes the path as a parameter.

::

    from labgrid.consoleloggingreporter import ConsoleLoggingReporter

    ConsoleLoggingReporter.start(".")

The Reporter can be stopped with a call to the stop function:

::

    from labgrid.consoleloggingreporter import ConsoleLoggingReporter

    ConsoleLoggingReporter.stop()


Stopping the ConsoleLoggingReporter if it has not been started will raise an
AssertionError, as will starting an already started StepReporter.



Environment Configuration
-------------------------
The environment configuration for a test environment consists of a YAML file
which contains targets, drivers and resources.
The invocation order of objects is important here since drivers may depend on
other drivers or resources.

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
     <target-2>:
       resources:
         <resources>
       drivers:
         <drivers>
     <more targets>
   options:
     <option-1 name>: <value for option-1>
     <more options>
   images:
     <image-1 name>: <absolute or relative path for image-1>
     <more images>
   tools:
     <tool-1 name>: <absolute or relative path for tool-1>
     <more tools>
   imports:
     - <import.py>

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

This configuration doesn't specifiy which :any:`RawSerialPort` to use for each
:any:`SerialDriver`, so it will cause an exception when instantiating the
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

The property name for the binding (e.g. `port` in the example above) is
documented for each individual driver under this chapter.

The YAML configuration file also supports templating for some substitutions,
these are:

- LG_* variables, are replaced with their respective LG_* environment variable
- BASE is substituted with the base directory of the YAML file.

As an example:

.. code-block:: yaml

  targets:
    main:
      resources:
        RemotePlace:
          name: !template $LG_PLACE
  tools:
    qemu_bin: !template "$BASE/bin/qemu-bin"

would resolve the qemu_bin path relative to the BASE dir of the YAML file and
try to use the RemotePlace with the name set in the LG_PLACE environment
variable.

Exporter Configuration
----------------------
The exporter is configured by using a YAML file (with a syntax similar to the
environment configs used for pytest) or by instantiating the :any:`Environment`
object.
To configure the exporter, you need to define one or more `resource groups`,
each containing one or more `resources`.
This allows the exporter to group resources for various usage scenarios, e.g.
all resources of a specific place or for a specific test setup.
For information on how the exporter fits into the rest of labgrid, see
:any:`remote-resources-and-places`.

The basic structure of an exporter configuration file is:

.. code-block:: yaml

   <group-1>:
     <resources>
   <group-2>:
     <resources>

The simplest case is with one group called "group1" containing a single
:any:`USBSerialPort`:

.. code-block:: yaml

   group1:
     USBSerialPort:
       match:
         '@sys_name': '3-1.3'

To reduce the amount of repeated declarations when many similar resources
need to be exported, the `Jinja2 template engine <http://jinja.pocoo.org/>`_
is used as a preprocessor for the configuration file:

.. code-block:: yaml

   ## Iterate from group 1001 to 1016
   # for idx in range(1, 17)
   {{ 1000 + idx }}:
     NetworkSerialPort:
       {host: rl1, port: {{ 4000 + idx }}}
     NetworkPowerPort:
       # if 1 <= idx <= 8
       {model: apc, host: apc1, index: {{ idx }}}
       # elif 9 <= idx <= 12
       {model: netio, host: netio4, index: {{ idx - 8 }}}
       # elif 13 <= idx <= 16
       {model: netio, host: netio5, index: {{ idx - 12 }}}
       # endif
   # endfor

Use ``#`` for line statements (like the for loops in the example) and ``##``
for line comments.
Statements like ``{{ 4000 + idx }}`` are expanded based on variables in the
Jinja2 template.
