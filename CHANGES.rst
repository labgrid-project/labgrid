Release 0.2.0 (unreleased)
--------------------------

New Features
~~~~~~~~~~~~

- The target now saves it's attached drivers, resources and protocols in a
  lookup table, avoiding the need of importing many Drivers and Protocols (see
  `Syntactic sugar for Targets`_)
- The new subcommand ``labgrid-client monitor`` shows resource or places
  changes as they happen, which is useful during development or debugging.
- The new `QEMUDriver` runs a system image in QEmu and implements the
  :any:`ConsoleProtocol` and :any:`PowerProtocol`.
  This allows using labgrid without any real hardware.
- The bootloader drivers now have a ``reset`` method.
- The `BareboxDriver`'s boot string is now configurable, which allows it to work
  with the ``quiet`` Linux boot parameter.
- The environment yaml file can now list Python files (under the 'imports' key).
  They are imported before constructing the Targets, which simplifies using
  custom Resources, Drivers or Strategies.
- The pytest plugin now stores metadata about the environment yaml file in the
  junit XML output.
- The ``labgrid-client`` tool now understands a ``--state`` option to
  transition to the provided state using a :any:`Strategy`.
  This requires an environment yaml file with a :any:`RemotePlace` Resources and
  matching Drivers.
- Resource matches for places configured in the coordinator can now have a
  name, allowing multiple resources with the same class.
- The new `Target.__getitem__` method makes writing using protocols less verbose.
- The `NetworkPowerDriver` now support the newer NETIO 4 models.
- The `ShellDriver` now supports configuring the login prompt timeout.
- The `SerialDriver` now supports using plain TCP instead of RFC 2217, which is
  needed from some console servers.
- Experimental: The labgrid-autoinstall tool was added (see below).

Incompatible Changes
~~~~~~~~~~~~~~~~~~~~

- When using the coordinator, it must be upgrade together with the clients
  because of the newly introduce match names.
- Resources and Drivers now need to be created with an explicit name
  parameter.
  It can be ``None`` to keep the old behaviour.
  See below for details.
- Classes derived from :any:`Resource` or :any:`Driver` now need to use
  ``@attr.s(cmp=False)`` instead of ``@attr.s`` because of a change in the
  attrs module version 17.1.0.

Syntactic sugar for Targets
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Targets are now able to retrieve requested drivers, resources or protocols by
name instead of by class.
This allows removing many imports, e.g.

::

   from labgrid.driver import ShellDriver

   shell = target.get_driver(ShellDriver)

becomes

::

   shell = target.get_driver("ShellDriver")

Also take a look at the examples, they have been ported to the new syntax as well.

Multiple Driver Instances
~~~~~~~~~~~~~~~~~~~~~~~~~

For some Protocols, it is useful to allow multiple instances.

DigitalOutputProtocol:
   A board may have two jumpers to control the boot mode in addition to a reset
   GPIO.
   Previously, it was not possible to use these on a single target.

ConsoleProtocol:
   Some boards have multiple console interfaces or expose a login prompt via a
   USB serial gadget.

PowerProtocol:
   In some cases, multiple power ports need to be controlled for one Target.

To support these use cases, Resources and Drivers must be created with a
name parameter.
When updating your code to this version, you can either simply set the name to
``None`` to keep the previous behaviour.
Alternatively, pass a string as the name.

Old:

.. code-block:: python

  >>> t = Target("MyTarget")
  >>> SerialPort(t)
  SerialPort(target=Target(name='MyTarget', env=None), state=<BindingState.bound: 1>, avail=True, port=None, speed=115200)
  >>> SerialDriver(t)
  SerialDriver(target=Target(name='MyTarget', env=None), state=<BindingState.bound: 1>, txdelay=0.0)

New (with name=None):

.. code-block:: python

  >>> t = Target("MyTarget")
  >>> SerialPort(t, None)
  SerialPort(target=Target(name='MyTarget', env=None), name=None, state=<BindingState.bound: 1>, avail=True, port=None, speed=115200)
  >>> SerialDriver(t, None)
  SerialDriver(target=Target(name='MyTarget', env=None), name=None, state=<BindingState.bound: 1>, txdelay=0.0)

New (with real names):

.. code-block:: python

  >>> t = Target("MyTarget")
  >>> SerialPort(t, "MyPort")
  SerialPort(target=Target(name='MyTarget', env=None), name='MyPort', state=<BindingState.bound: 1>, avail=True, port=None, speed=115200)
  >>> SerialDriver(t, "MyDriver")
  SerialDriver(target=Target(name='MyTarget', env=None), name='MyDriver', state=<BindingState.bound: 1>, txdelay=0.0)

Auto-Installer Tool
~~~~~~~~~~~~~~~~~~~

To simplify using labgrid for provisioning several boards in parallel, the
``labgrid-autoinstall`` tool was added.
It reads a YAML file defining several targets and a Python script to be run for
each board.
Interally, it spawns a child process for each target, which waits until a matching
resource becomes available and then executes the script.

For example, this makes it simple to load a bootloader via the
:any:`BootstrapProtocol`, use the :any:`AndroidFastbootDriver` to upload a
kernel with initramfs and then write the target's eMMC over a USB Mass Storage
gadget.

.. note::
  ``labgrid-autoinstall`` is still experimental and no documentation has been written.

Release 0.1.0 (released May 11, 2017)
-------------------------------------

This is the initial release of labgrid.
