Development
============
The first step is to install labgrid into a local virtualenv.

Installation
------------

Clone the git repository:

.. code-block:: bash

   git clone https://github.com/labgrid-project/labgrid && cd labgrid

Create and activate a virtualenv for labgrid:

.. code-block:: bash

   virtualenv -p python3 venv
   source venv/bin/activate

Install required dependencies:

.. code-block:: bash

   sudo apt install libow-dev

Install the development requirements:

.. code-block:: bash

   pip install -r dev-requirements.txt

Install labgrid into the virtualenv in editable mode:

.. code-block:: bash

   pip install -e .

Tests can now be run via:

.. code-block:: bash

   python -m pytest --lg-env <config>

Writing a Driver
----------------

To develop a new driver for labgrid, you need to decide which protocol to
implement, or implement your own protocol.
If you are unsure about a new protocol's API, just use the driver directly from
the client code, as deciding on a good API will be much easier when another
similar driver is added.

Labgrid uses the `attrs library <https://attrs.readthedocs.io>`_ for internal
classes.
First of all import attr, the protocol and the common driver class
into your new driver file.

::

    import attr

    from labgrid.driver.common import Driver
    from labgrid.protocol import ConsoleProtocol

Next, define your new class and list the protocols as subclasses of the new
driver class.
Try to avoid subclassing existing other drivers, as this limits the flexibility
provided by connecting drivers and resources on a given target at runtime.

::

    import attr

    from labgrid.driver.common import Driver
    from labgrid.protocol import ConsoleProtocol

    @attr.s(cmp=False)
    class ExampleDriver(Driver, ConsoleProtocol):
        pass

The ConsoleExpectMixin is a mixin class to add expect functionality to any
class supporting the :any:`ConsoleProtocol` and has to be the first item in the
subclass list.
Using the mixin class allows sharing common code, which would otherwise need to
be added into multiple drivers.

::

    import attr

    from labgrid.driver.common import Driver
    from labgrid.driver.consoleexpectmixin import ConsoleExpectMixin
    from labgrid.protocol import ConsoleProtocol

    @attr.s(cmp=False)
    class ExampleDriver(ConsoleExpectMixin, Driver, ConsoleProtocol)
        pass

Additionally the driver needs to be registered with the :any:`target_factory`
and provide a bindings dictionary, so that the :any:`Target` can resolve
dependencies on other drivers or resources.

::

    import attr

    from labgrid.factory import target_factory
    from labgrid.driver.common import Driver
    from labgrid.driver.consoleexpectmixin import ConsoleExpectMixin
    from labgrid.protocol import ConsoleProtocol

    @target_factory.reg_driver
    @attr.s(cmp=False)
    class ExampleDriver(ConsoleExpectMixin, Driver, ConsoleProtocol)
        bindings = { "port": SerialPort }
        pass

The listed resource :code:`SerialPort` will be bound to :code:`self.port`,
making it usable in the class.
Checks are performed that the target which the driver binds to has a SerialPort,
otherwise an error will be raised.

If your driver can support alternative resources, you can use a set of classes
instead of a single class::

    bindings = { "port": {SerialPort, NetworkSerialPort}}

Optional bindings can be declared by including ``None`` in the set::

    bindings = { "port": {SerialPort, NetworkSerialPort, None}}

If you need to do something during instantiation, you need to add a
:code:`__attr_post_init__` method (instead of the usual :code:`__init__` used
for non-attr-classes).
The minimum requirement is a call to :code:`super().__attr_post_init__()`.

::

    import attr

    from labgrid.factory import target_factory
    from labgrid.driver.common import Driver
    from labgrid.driver.consoleexpectmixin import ConsoleExpectMixin
    from labgrid.protocol import ConsoleProtocol

    @target_factory.reg_driver
    @attr.s(cmp=False)
    class ExampleDriver(ConsoleExpectMixin, Driver, ConsoleProtocol)
        bindings = { "port": SerialPort }

        def __attr_post_init__(self):
            super().__attr_post_init__()

All that's left now is to implement the functionality described by the used
protocol, by using the API of the bound drivers and resources.

Writing a Resource
-------------------

To add a new resource to labgrid, we import attr into our new resource file.
Additionally we need the :any:`target_factory` and the common Resource class.

::

    import attr

    from labgrid.factory import target_factory
    from labgrid.driver.common import Resource

Next we add our own resource with the :code:`Resource` parent class and
register it with the :any:`target_factory`.

::

    import attr

    from labgrid.factory import target_factory
    from labgrid.driver.common import Resource


    @target_factory.reg_resource
    @attr.s(cmp=False)
    class ExampleResource(Resource):
        pass

All that is left now is to add attributes via :code:`attr.ib()` member
variables.

::

    import attr

    from labgrid.factory import target_factory
    from labgrid.driver.common import Resource


    @target_factory.reg_resource
    @attr.s(cmp=False)
    class ExampleResource(Resource):
        examplevar1 = attr.ib()
        examplevar2 = attr.ib()

The :code:`attr.ib()` style of member definition also supports defaults and
validators, see the `attrs documentation <https://attrs.readthedocs.io/en/stable/>`_.

Writing a Strategy
------------------

Labgrid only offers two basic strategies, for complex use cases a customized
strategy is required.
Start by creating a strategy skeleton:

::

    import enum

    import attr

    from labgrid.step import step
    from labgrid.driver.common import Strategy

    class Status(enum.Enum):
        unknown = 0

    class MyStrategy(Strategy):
        bindings = {
        }

        status = attr.ib(default=Status.unknown)

        @step
        def transition(self, status, *, step):
            if not isinstance(status, Status):
                status = Status[status]
            if status == Status.unknown:
                raise StrategyError("can not transition to {}".format(status))
            elif status == self.status:
                step.skip("nothing to do")
                return  # nothing to do
            else:
                raise StrategyError(
                    "no transition found from {} to {}".
                    format(self.status, status)
                )
            self.status = status


The ``bindings`` variable needs to declare the drivers necessary for the
strategy, usually one for power, boot loader and shell.
The ``Status`` class needs to be extended to cover the states of your strategy,
then for each state an ``elif`` entry in the transition function needs to be
added.

Lets take a look at the builtin `BareboxStrategy`. The Status enum for Barebox:

::

   class Status(enum.Enum):
       unknown = 0
       barebox = 1
       shell = 2

defines 2 custom states and the `unknown` state as the start point.
These two states are handled in the transition function:

::

    elif status == Status.barebox:
        # cycle power
        self.target.activate(self.power)
        self.power.cycle()
        # interrupt barebox
        self.target.activate(self.barebox)
    elif status == Status.shell:
        # tansition to barebox
        self.transition(Status.barebox)
        self.barebox.boot("")
        self.barebox.await_boot()
        self.target.activate(self.shell)

Here the `barebox` state simply cycles the board and activates the driver, while
the `shell` state uses the barebox state to cycle the board and than boot the
linux kernel.

.. _contributing:

Contributing
------------

Thank you for thinking about contributing to labgrid!
Some different backgrounds and use-cases are essential for making labgrid work
well for all users.

The following should help you with submitting your changes, but don't let these
guidelines keep you from opening a pull request.
If in doubt, we'd prefer to see the code earlier as a work-in-progress PR and
help you with the submission process.

Workflow
~~~~~~~~

- Changes should be submitted via a `GitHub pull request
  <https://github.com/labgrid-project/labgrid/pulls>`_.
- Try to limit each commit to a single conceptual change.
- Add a signed-of-by line to your commits according to the `Developer's
  Certificate of Origin` (see below).
- Check that the tests still work before submitting the pull request. Also
  check the CI's feedback on the pull request after submission.
- When adding new drivers or resources, please also add the corresponding
  documentation and test code.
- If your change affects backward compatibility, describe the necessary changes
  in the commit message and update the examples where needed.

Code
~~~~

- Follow the :pep:`8` style.
- Use attr.ib attributes for public attributes of your drivers and resources.
- Use `isort <https://pypi.python.org/pypi/isort>`_ to sort the import
  statements.

Documentation
~~~~~~~~~~~~~
- Use `semantic linefeeds
  <http://rhodesmill.org/brandon/2012/one-sentence-per-line/>`_ in .rst files.

Developer's Certificate of Origin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Labgrid uses the `Developer's Certificate of Origin 1.1
<https://developercertificate.org/>`_ with the same `process
<https://www.kernel.org/doc/html/latest/process/submitting-patches.html#sign-your-work-the-developer-s-certificate-of-origin>`_
as used for the Linux kernel:

  Developer's Certificate of Origin 1.1

  By making a contribution to this project, I certify that:

  (a) The contribution was created in whole or in part by me and I
      have the right to submit it under the open source license
      indicated in the file; or

  (b) The contribution is based upon previous work that, to the best
      of my knowledge, is covered under an appropriate open source
      license and I have the right under that license to submit that
      work with modifications, whether created in whole or in part
      by me, under the same open source license (unless I am
      permitted to submit under a different license), as indicated
      in the file; or

  (c) The contribution was provided directly to me by some other
      person who certified (a), (b) or (c) and I have not modified
      it.

  (d) I understand and agree that this project and the contribution
      are public and that a record of the contribution (including all
      personal information I submit with it, including my sign-off) is
      maintained indefinitely and may be redistributed consistent with
      this project or the open source license(s) involved.

Then you just add a line (using ``git commit -s``) saying:

  Signed-off-by: Random J Developer <random@developer.example.org>

using your real name (sorry, no pseudonyms or anonymous contributions).

.. _ideas:

Ideas
-----

.. please keep these sorted alphabetically

Driver Priorities
~~~~~~~~~~~~~~~~~

In more complex use-cases, we often have multiple drivers implementing the same
Protocols on the same :any:`Target`. For example:

CommandProtocol (ShellDriver and SSHDriver):
   The SSHDriver may not be active all the time, but should be preferred when it
   is.

ResetProtocol (DigitalOutputResetDriver and NetworkPowerPort via power cycling):
   This will occour when we implement the `ResetProtocol`_ as below.
   The real reset driver should be preferred in that case.

To avoid a central precedence list (which would be problematic for third-party
drivers), each driver should declare its precedence per protocol relative other
drivers by referencing them by class name.
This way, the Target can sort them at runtime.

Driver Preemption
~~~~~~~~~~~~~~~~~

To allow better handling of unexpected reboots or crashes, inactive Drivers
could register callbacks on their providers (for example the BareboxDriver it's
ConsoleProtocol).
These callbacks would look for indications that the Target has changed state
unexpectedly (by looking for the bootloader startup messages, in this case).
The inactive Driver could then cause a preemption and would be activated.
The current caller of the originally active driver would be notified via an
exception.

File Transfer to Exporters
~~~~~~~~~~~~~~~~~~~~~~~~~~

Currently, the exporter and client expect to have a shared filesystem (see for
example how the :any:`AndroidFastbootDriver` works when accessing a
:any:`NetworkAndroidFastboot` resource).
To remove this limitation, we should have a common way to make files available
to the exporter, possibly by generating a hash locally and rsyncing new files to
the exporter.

Remote Target Reservation
~~~~~~~~~~~~~~~~~~~~~~~~~

For integration with CI systems (like Jenkins), it would help if the CI job
could reserve and wait for a specific target.
This could be done by managing a list of waiting users in the coordinator and
notifying the current user on each invocation of labgrid-client that another
user is waiting.
The reservation should expire after some time if it is not used to lock the
target after it becomes available.

ResetProtocol
~~~~~~~~~~~~~

Resetting a board is a distinct operation from cycling the power and is often
triggered by pushing a button (automated via a relays or FET).
If a real reset is unavailable, power cycling could be used to emulate the reset.
Currently, the :any:`DigitalOutputPowerDriver` implements the
:any:`PowerProtocol` instead, mixing the two aspects.

To handle falling back to emulation via the PowerProtocol nicely, we would need
to implement `Driver Priorities`_

Step Tracing
~~~~~~~~~~~~

The Step infrastructure already collects timing and nesting information on
executed commands, but is currently only used for in pytest or via the
standalone StepReporter.
By writing these events to a file (or sqlite database) as a trace, we can
collect data over multiple runs for later analysis.
This would become more useful by passing recognized events (stack traces,
crashes, ...) and benchmark results via the Step infrastructure.

Target Feature Flags
~~~~~~~~~~~~~~~~~~~~

It would be useful to support configuring feature flags in the target YAML
definition.
Then individual tests could be skipped if a required feature is unavailable on
the current target without manually modifying the test suite.
