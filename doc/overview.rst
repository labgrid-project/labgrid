.. _overview:

Overview
========

Architecture
------------

labgrid can be used in several ways:

- on the command line to control individual embedded systems during development
  ("board farm")
- via a pytest plugin to automate testing of embedded systems
- as a python library in other programs

In the labgrid library, a controllable embedded system is represented as a
:any:`Target`.
`Targets` normally have several :any:`Resource` and :any:`Driver` objects,
which are used to store the board-specific information and to implement actions
on different abstraction levels.
For cases where a board needs to be transitioned to specific states (such as
`off`, `in bootloader`, `in Linux shell`), a :any:`Strategy` (a special kind of
`Driver`) can be added to the `Target`.

While labgrid comes with implementations for some resources, drivers and
strategies, custom implementations for these can be registered at runtime.
It is expected that for complex use-cases, the user would implement and
register a custom `Strategy` and possibly some higher-level `Drivers`.

.. _overview-resources:

Resources
~~~~~~~~~

`Resources` are passive and only store the information to access the
corresponding part of the `Target`.
Typical examples of resources are :any:`RawSerialPort`, :any:`NetworkPowerPort`
and :any:`AndroidUSBFastboot`.

An important type of `Resources` are :any:`ManagedResources <ManagedResource>`.
While normal `Resources` are always considered available for use and have fixed
properties (such as the ``/dev/ttyUSB0`` device name for a
:any:`RawSerialPort`), the `ManagedResources` are used to represent interfaces
which are discoverable in some way.
They can appear/disappear at runtime and have different properties each time
they are discovered.
The most common examples of `ManagedResources` are the various USB resources
discovered using udev, such as :any:`USBSerialPort`, :any:`IMXUSBLoader` or
:any:`AndroidUSBFastboot` (see the :ref:`udev matching section <udev-matching>`).

Drivers and Protocols
~~~~~~~~~~~~~~~~~~~~~

A labgrid :any:`Driver` uses one (or more) `Resources` and/or other, lower-level
`Drivers` to perform a set of actions on a `Target`.
For example, the :any:`NetworkPowerDriver` uses a :any:`NetworkPowerPort`
resource to control the `Target's` power supply.
In this case, the actions are "on", "off", "cycle" and "get".

As another example, the :any:`ShellDriver` uses any driver implementing the
:any:`ConsoleProtocol` (such as a :any:`SerialDriver`, see below).
The `ConsoleProtocol` allows the `ShellDriver` to work with any specific method
of accessing the board's console (locally via USB, over the network using a
console server or even an external program).
At the `ConsoleProtocol` level, characters are sent to and received from the
target, but they are not yet interpreted as specific commands or their output.

The `ShellDriver` implements the higher-level :any:`CommandProtocol`, providing
actions such as "run" or "run_check".
Internally, it interacts with the Linux shell on the target board.
For example, it:

- waits for the login prompt
- enters user name and password
- runs the requested shell command (delimited by marker strings)
- parses the output
- retrieves the exit status

Other drivers, such as the :any:`SSHDriver`, also implement the
`CommandProtocol`.
This way, higher-level code (such as a test suite), can be independent of the
concrete control method on a given board.

Binding and Activation
~~~~~~~~~~~~~~~~~~~~~~

When a `Target` is configured, each driver is "bound" to the resources (or
other drivers) required by it.
Each `Driver` class has a "bindings" attribute, which declares which
`Resources` or `Protocols` it needs and under which name they should be
available to the `Driver` instance.
The binding resolution is handled by the `Target` during the initial
configuration and results in a directed, acyclic graph of resources and
drivers.
During the lifetime of a `Target`, the bindings are considered static.

In most non-trivial target configurations, some drivers are mutually exclusive.
For example, a `Target` may have both a :any:`ShellDriver` and a :any:`BareboxDriver`.
Both bind to a driver implementing the `ConsoleProtocol` and provide the
`CommandProtocol`.
Obviously, the board cannot be in the bootloader and in Linux at the same time,
which is represented in labgrid via the :any:`BindingState` (`bound`/`active`).
If, during activation of a driver, any other driver in its bindings is not
active, they will be activated as well.

Activating and deactivating `Drivers` is also used to handle `ManagedResources`
becoming available/unavailable at runtime.
If some resources bound to by the activating drivers are currently unavailable,
the `Target` will wait for them to appear (with a per resource timeout).
A realistic sequence of activation might look like this:

- enable power (:any:`PowerProtocol.on`)
- activate the :any:`IMXUSBDriver` driver on the target (this will wait for the
  :any:`IMXUSBLoader` resource to be available)
- load the bootloader (:any:`BootstrapProtocol.load`)
- activate the :any:`AndroidFastbootDriver` driver on the target (this will
  wait for the :any:`AndroidUSBFastboot` resource to be available)
- boot the kernel (:any:`AndroidFastbootDriver.boot`)
- activate the :any:`ShellDriver` driver on the target (this will wait for the
  :any:`USBSerialPort` resource to be available and log in)

Any `ManagedResources` which become unavailable at runtime will automatically
deactivate the dependent drivers.

Multiple Drivers and Names
~~~~~~~~~~~~~~~~~~~~~~~~~~

Each driver and resource can have an optional name. This parameter is required
for all manual creations of drivers and resources. To manually bind to a
specific driver set a binding mapping before creating the driver:

.. doctest::

  >>> from labgrid import Target
  >>> from labgrid.resource import SerialPort
  >>> from labgrid.driver import SerialDriver
  >>>
  >>> t = Target("Test")
  >>> SerialPort(t, "First")
  SerialPort(target=Target(name='Test', env=None), name='First', state=<BindingState.bound: 1>, avail=True, port=None, speed=115200)
  >>> SerialPort(t, "Second")
  SerialPort(target=Target(name='Test', env=None), name='Second', state=<BindingState.bound: 1>, avail=True, port=None, speed=115200)
  >>> t.set_binding_map({"port": "Second"})
  >>> sd = SerialDriver(t, "Driver")
  >>> sd
  SerialDriver(target=Target(name='Test', env=None), name='Driver', state=<BindingState.bound: 1>, txdelay=0.0, timeout=3.0)
  >>> sd.port
  SerialPort(target=Target(name='Test', env=None), name='Second', state=<BindingState.bound: 1>, avail=True, port=None, speed=115200)

Priorities
~~~~~~~~~~
Each driver supports a priorities class variable.
This allows drivers which implement the same protocol to add a priority option
to each of their protocols.
This way a `NetworkPowerDriver` can implement the `ResetProtocol`, but if another
`ResetProtocol` driver with a higher protocol is available, it will be selected
instead.

.. note::
  Priority resolution only takes place if you have multiple drivers
  which implement the same protocol and you are not fetching them by
  name.

The target resolves the driver priority via the Method Resolution Order (MRO)
of the driver's base classes.
If a base class has a `priorities` dictionary which contains the requested
Protocol as a key, that priority is used.
Otherwise, `0` is returned as the default priority.

To set the priority of a protocol for a driver, add a class variable with the
name `priorities`, e.g.

.. testcode::

   import attr
   from labgrid.driver import Driver
   from labgrid.protocol import PowerProtocol, ResetProtocol

   @attr.s
   class NetworkPowerDriver(Driver, PowerProtocol, ResetProtocol):
       priorities = {PowerProtocol: -10}

Strategies
~~~~~~~~~~

Especially when using labgrid from pytest, explicitly controlling the board's
boot process can distract from the individual test case.
Each :any:`Strategy` implements the board- or project-specific actions necessary to
transition from one state to another.
labgrid includes the :any:`BareboxStrategy` and the :any:`UBootStrategy`, which
can be used as-is for simple cases or serve as an example for implementing a
custom strategy.

`Strategies` themselves are not activated/deactivated.
Instead, they control the states of the other drivers explicitly and execute
actions to bring the target into the requested state.

See the strategy example (``examples/strategy``) and the included strategies in
``labgrid/strategy`` for some more information.

For more information on the reasons behind labgrid's architecture, see
:doc:`design_decisions`.

.. _remote-resources-and-places:

Remote Resources and Places
---------------------------

labgrid contains components for accessing resources which are not directly
accessible on the local machine.
The main parts of this are:

labgrid-coordinator
  Clients and exporters connect to the coordinator to publish resources, manage
  place configuration and handle mutual exclusion.

:ref:`labgrid-exporter` (CLI)
  Exports explicitly configured local resources to the coordinator and monitors
  these for changes in availability or parameters.

:ref:`labgrid-client` (CLI)
  Configures places (consisting of exported resources) and allows command line
  access to some actions (such as power control, bootstrap, fastboot and the
  console).

RemotePlace (managed resource)
  When used in a `Target`, the RemotePlace expands to the resources configured
  for the named places.

These components communicate over `gRPC <https://grpc.io/>`_. The coordinator
acts as a gRPC server to which client and exporter connect.

The following sections describe the responsibilities of each component. See
:ref:`remote-usage` for usage information.

.. _overview-coordinator:

Coordinator
~~~~~~~~~~~

The `Coordinator` is implemented as a gRPC server and is started as a separate
process.
It provides separate RPC methods for the exporters and clients.

The coordinator keeps a list of all resources for clients and
notifies them of changes as they occur.
The resource access from clients does not pass through the coordinator, but is
instead done directly from client to exporter, avoiding the need to specify new
interfaces for each resource type.

The coordinator also manages the registry of "places".
These are used to configure which resources belong together from the user's
point of view.
A `place` can be a generic rack location, where different boards are connected
to a static set of interfaces (resources such as power, network, serial
console, …).

Alternatively, a `place` can also be created for a specific board, for example
when special interfaces such as GPIO buttons need to be controlled and they are
not available in the generic locations.

Each place can have aliases to simplify accessing a specific board (which might
be moved between generic places).
It also has a comment, which is used to store a short description of the
connected board.

To support selecting a specific place from a group containing similar or
identical hardware, key-value tags can be added to places and used for
scheduling.

Finally, a place is configured with one or more `resource matches`.
A resource match pattern has the format ``<exporter>/<group>/<class>/<name>``,
where each component may be replaced with the wildcard ``*``.
The ``/<name>`` part is optional and can be left out to match all resources of a class.

Some commonly used match patterns are:

\*/1001/\*
  Matches all resources in groups named 1001 from all exporters.

\*/1001/NetworkPowerPort
  Matches only the NetworkPowerPort resource in groups named 1001 from all
  exporters.
  This is useful to exclude a NetworkSerialPort in group 1001 in cases where
  the serial console is connected somewhere else (such as via USB on a
  different exporter).

exporter1/hub1-port1/\*
  Matches all resources exported from exporter1 in the group hub1-port1.
  This is an easy way to match several USB resources related to the same board
  (such as a USB ROM-Loader interface, Android fastboot and a USB serial gadget
  in Linux).

To avoid conflicting access to the same resources, a place must be `acquired`
before it is used and the coordinator also keeps track of which user on which
client host has currently acquired the place.
The resource matches are only evaluated while a place is being acquired and cannot be
changed until it is `released` again.

.. _overview-exporter:

Exporter
~~~~~~~~
An exporter registers all its configured resources when it connects to the
router and updates the resource parameters when they change (such as
(dis-)connection of USB devices).
Internally, the exporter uses the normal :any:`Resource` (and
:any:`ManagedResource`) classes as the rest of labgrid.
By using `ManagedResources`, availability and parameters for resources such as
USB serial ports are tracked and sent to the coordinator.

For some specific resources (such as :any:`USBSerialPorts <USBSerialPort>`),
the exporter uses external tools to allow access by clients (``ser2net`` in the
serial port case).

Resources which do not need explicit support in the exporter, are just
published as declared in the configuration file.
This is useful to register externally configured resources such as network
power switches or serial port servers with a labgrid coordinator.

.. note::
  Users will require SSH access to the exporter to access services and command
  line utilities. You also have to ensure that users can access usb devices for
  i.e. imx-usb-loader. To test a SSH jump to a device over the exporter outside
  of labgrid, `ssh -J EXPORTER USER@DEVICE` can be used.

.. _overview-client:

Client
~~~~~~
The client requests the current lists of resources and places from the
coordinator when it connects to it and then registers for change events.
Most of its functionality is exposed via the `labgrid-client` CLI tool.
It is also used by the :any:`RemotePlace` resource (see below).

Besides viewing the list of `resources`, the client is used to configure and
access `places` on the coordinator.
For more information on using the CLI, see the manual page for
:ref:`labgrid-client`.

RemotePlace
~~~~~~~~~~~
To use the resources configured for a `place` to control the corresponding
board (whether in pytest or directly with the labgrid library), the
:any:`RemotePlace` resource should be used.
When a `RemotePlace` is configured for a `Target`, it will create a client
connection to the coordinator, create additional resource objects for those
configured for that place and keep them updated at runtime.

The additional resource objects can be bound to by drivers as normal and the
drivers do not need to be aware that they were provided by the coordinator.
For resource types which do not have an existing, network-transparent protocol
(such as USB ROM loaders or JTAG interfaces), the driver needs to be aware of
the mapping done by the exporter.

For generic USB resources, the exporter for example maps a
:any:`AndroidUSBFastboot` resource to a :any:`RemoteAndroidUSBFastboot` resource and
adds a hostname property which needs to be used by the client to connect to the
exporter.
To avoid the need for additional remote access protocols and authentication,
labgrid currently expects that the hosts are accessible via SSH and that any
file names refer to a shared filesystem (such as NFS or SMB).

.. note::
  Using SSH's session sharing (``ControlMaster auto``, ``ControlPersist``, …)
  makes `RemotePlaces` easy to use even for exporters with require passwords or
  more complex login procedures.

  For exporters which are not directly accessible via SSH, add the host to your
  .ssh/config file, with a ProxyCommand when need.

.. _overview-proxy-mechanism:

Proxy Mechanism
~~~~~~~~~~~~~~~

Both client and exporter support the proxy mechanism which uses SSH to tunnel
connections to a remote host. To enable and force proxy mode on the exporter use
the :code:`-i` or :code:`--isolated` command line option. This indicates to clients that all
connections to remote resources made available by this exporter need to be
tunneled using a SSH connection.

On the other hand, clients may need to access the remote coordinator
infrastructure using a SSH tunnel. In this case the :code:`LG_PROXY` environment
variable needs to be set to the remote host which should tunnel the connection
to the coordinator. The client then forwards all network traffic -
client-to-coordinator and client-to-exporter - through SSH, via their
respective proxies. This means that with :code:`LG_PROXY` and
:code:`LG_COORDINATOR` labgrid can be used fully remotely with only a SSH
connection as a requirement.

.. note::
  Labgrid prefers to connect to an exporter-defined proxy over using the
  LG_PROXY variable. This means that a correct entry for the exporter needs to
  be set up in the ~/.ssh/config file. You can view exporter proxies with
  :code:`labgrid-client -v resources`.

One remaining issue here is the forward of UDP connections, which is currently
not possible. UDP connections are used by some of the power backends in the
form of SNMP.
