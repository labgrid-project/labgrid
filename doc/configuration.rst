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
A USBSerialPort describes a serial port which is identified by matching udev
properties. This allows an identification through hot plugging or rebooting.

.. code-block:: yaml

   NetworkSerialPort:
     match:
       ID_SERIAL_SHORT: P-00-00682
     speed: 115200

The example would search for a USB serial converter with the key
`ID_SERIAL_SHORT` and the value `P-00-00682` and use it with a baud rate
of 115200.

- match (str): key and value for a udev match, see `Udev Matching`_
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

Udev Matching
~~~~~~~~~~~~~
Udev matching allows labgrid to identify resources via their udev properties.
Any udev property key and value can be used, path matching USB devices is
allowed as well. This allows the export of a specific USB hub port or the
correct identification of a USB serial converter across computers.

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

Implements:
  - :any:`ConsoleProtocol`

Arguments:
  - None

ShellDriver
~~~~~~~~~~~

Binds to:
  - :any:`ConsoleProtocol`

Implements:
  - :any:`CommandProtocol`

Arguments:
  - prompt (regex): prompt to match after logging in 
  - login_prompt (regex): match for the login prompt
  - username (str): username to use during login
  - password (str): password to use during login
  - keyfile (str): optional keyfile to upload after login, making the
    :any:`SSHDriver` usable

Strategies
~~~~~~~~~~

Environment Configuration
-------------------------

Exporter Configuration
----------------------

