Overview
========

Installation
------------

The default installation is available via PyPI:

.. code-block:: bash

    $ pip install labgrid

or by cloning the repository and installing manually:

.. code-block:: bash

    $ git clone https://github.com/labgrid-project/labgrid
    $ cd labgrid && python3 setup.py install

Extra requires
~~~~~~~~~~~~~~
Labgrid supports different extras:

- onewire: install onewire support, requires ``onewire>=0.0.2`` from PyPI and
  additionally ``libow-dev`` on debian based distributions.
- coordinator: installs required depencies to start a crossbar coordinator

The extras can be selected by passing them after the package name in square
brackets:

.. code-block:: bash

    $ pip install labgrid[onewire]

or to enable both:

.. code-block:: bash

    $ pip install labgrid[onewire,coordinator]

Depending on the used shell settings, the brackets may have to be escaped via ``\``.

Architecture
------------

Labgrid can be used in several ways:

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

Resources
~~~~~~~~~

`Resources` are passive and only store the information to access the
corresponding part of the `Target`.
Typical examples of resources are :any:`RawSerialPort`, :any:`NetworkPowerPort`
and :any:`AndroidFastboot`.

An important type of `Resources` are :any:`ManagedResources <ManagedResource>`.
While normal `Resources` are always considered available for use and have fixed
properties (such as the ``/dev/ttyUSB0`` device name for a
:any:`RawSerialPort`), the `ManagedResources` are used to represent interfaces
which are discoverable in some way.
They can appear/disappear at runtime and have different properties each time
they are discovered.
The most common examples of `ManagedResources` are the various USB resources
discovered using udev, such as :any:`USBSerialPort`, :any:`IMXUSBLoader` or
:any:`AndroidFastboot`.

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
At the `ConsoleProtocol` level, character are send to and received from the
target, but they are not yet interpreted as specific commands or their output.

The `ShellDriver` implements the higher-level :any:`CommandProtocol`, providing
actions such as "run" or "run_check".
Internally, it interacts with Linux shell on the target board.
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
If, during activation of a driver, any other driver in it's bindings is not
active, they are activated as well.

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
  wait for the :any:`AndroidFastboot` resource to be available)
- boot the kernel (:any:`AndroidFastbootDriver.boot`)
- activate the :any:`ShellDriver` driver on the target (this will wait for the
  :any:`USBSerialPort` resource to be available and log in)

Any `ManagedResources` which become unavailable at runtime will automatically
deactivate the dependant drivers.

Strategies
~~~~~~~~~~

Especially when using labgrid from pytest, explicitly controlling the board's
boot process can distract from the individual test case.
Each :any:`Strategy` implements the board- or project-specific actions necessary to
transition from one state to another.
Labgrid includes the :any:`BareboxStrategy` and the :any:`UBootStrategy`, which
can be used as-is for simple cases or serve as an example for implementing a
custom strategy.

`Strategies` themselves are not activated/deactivated.
Instead, they control the states of the other drivers explicitly and execute
actions to bring the target into the requested state.

See the strategy example (``examples/strategy``) and the included strategies in
``labgrid/strategy`` for some more information.

For more information on the reasons behind labgrid's architecture, see
:doc:`design_decisions`.

Remote Resources and Places
---------------------------

Labgrid contains components for accessing resources which are not directly
accessible on the local machine.
The main parts of this are:

labgrid-coordinator (crossbar component)
  Clients and exporters connect to the coordinator to publish resources, manage
  place configuration and handle mutual exclusion.

labgrid-exporter (CLI)
  Exports explicitly configured local resources to the coordinator and monitors
  these for changes in availability or parameters.

labgrid-client (CLI)
  Configures places (consisting of exported resources) and allows command line
  access to some actions (such as power control, bootstrap, fastboot and the
  console).

RemotePlace (managed resource)
  When used in a `Target`, the RemotePlace expands to the resources configured
  for the named places.

Coordinator
~~~~~~~~~~~

Exporter
~~~~~~~~

Client
~~~~~~

RemotePlace
~~~~~~~~~~~

Standalone
----------

The Labgrid library consists of a set of fixtures which implement the automatic
creation of targets, drivers and synchronisation helpers. The configuration file
`environment.yaml` specifies how the library assembles these fixtures into
working targets. Certain functionality depends upon the availability of a
specific resource or driver, the parser will throw an error and a helpful
message if this is the case.

Scripting usage
~~~~~~~~~~~~~~~

Although the environment creates all the instances by itself, the test editor
still has to create the appropriate fixtures for each device. The environment,
the targets can be extracted by using the function `get_target`.

Example:
::

   from labgrid import Environment

   env = Environment()
   t1 = environment.get_target('target1')
   t2 = environment.get_target('target2')

Pytest Plugin
-------------
Labgrid provides a pytest-plugin as an entry point. It needs the --env-config=
configuration option to be set and creates environment and targets by itself.
