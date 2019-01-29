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
:code:`__attrs_post_init__` method (instead of the usual :code:`__init__` used
for non-attr-classes).
The minimum requirement is a call to :code:`super().__attrs_post_init__()`.

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

        def __attrs_post_init__(self):
            super().__attrs_post_init__()

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
       off = 1
       barebox = 2
       shell = 3

defines 3 custom states and the `unknown` state as the start point.
These three states are handled in the transition function:

::

    elif status == Status.off:
        self.target.deactivate(self.barebox)
        self.target.deactivate(self.shell)
        self.target.activate(self.power)
        self.power.off()
    elif status == Status.barebox:
        self.transition(Status.off)
        # cycle power
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
linux kernel. The `off` states switch the power off.

Graph Strategies
----------------

Graph Strategies are made for more complex strategies, with multiple, on each
other depending, states.

All states **HAVE TO**:
  1. Be a method of a `GraphStrategy` subclass
  2. Use this prototype: `def state_$STATENAME(self):`
  3. Not call `transition()` in its state definition

Every Graph Strategy graph has to have exactly one root state.
A root state is a state that has no dependencies.
If `invalidate()` is overridden the super method must be called.

.. code-block:: python

    # conftest.py
    from labgrid.strategy import GraphStrategy


    class TestStrategy(GraphStrategy):
        def state_Root(self):
            pass

        @GraphStrategy.depends('Root')
        def state_A1(self):
            pass

        @GraphStrategy.depends('Root')
        def state_A2(self):
            pass

        @GraphStrategy.depends('A1', 'A2')
        def state_B(self):
            pass

Graph Stategies allow to specify multiple paths to states.
The first argument of `@GraphStrategy.depends()` becomes part of the default
path.
If a different path should be followed the keyword argument `via` can be used
on `transition()`.

.. code-block:: python

    # test_feature.py
    def test_feature(graph_strategy):
        graph_strategy.transition('B')  #  returns: ['A1', 'B']
        graph_strategy.transition('B')  #  returns: []
        graph_strategy.transition('B', via=['A2'])  #  returns: ['Root', 'A2', 'B']

`pytest fixtures <https://docs.pytest.org/en/latest/fixture.html>`_ can be used
to `transition()` into the designated state before a test is executed.
Use `transition('my_state', via=...)` to follow a (non-default) path, e.g. an
alternative boot method.

.. code-block:: python

    # render graph to png
    >>> graph_strategy.graph.render('filename')
    'filename.png'

.. image:: res/graphstrategy-1.png

.. image:: res/graphstrategy-2.png


SSHManager
----------

Labgrid provides a SSHManager to allow connection reuse with control sockets.
To use the SSHManager in your code, import it from `labgrid.util.ssh`:

.. code-block:: python

   from labgrid.util.ssh import sshmanager

you can now request or remove forwards:

.. code-block:: python

   from labgrid.util.ssh import sshmanager

   localport = sshmanager.request_forward('somehost', 3000)

   sshmanager.remove_forward('somehost', 3000)

or get and put files:

.. code-block:: python

   from labgrid.util.ssh import sshmanager

   sshmanager.put_file('somehost', '/path/to/local/file', '/path/to/remote/file')

ManagedFile
-----------
While the `SSHManager` exposes a lower level interface to use SSH Connections,
the ManagedFile provides a higher level interface for file upload to another
host. It is meant to be used in conjunction with a remote resource, and store
the file on the remote host with the following pattern:

.. code-block:: bash

   /tmp/labgrid-<username>/<sha256sum>/<filename>

Additionally it provides `get_remote_path()` to retrieve the complete file path,
to easily employ it for driver implementations.
To use it in conjunction with a `Resource` and a file:

.. code-block:: python

   from labgrid.util.managedfile import ManagedFile

   mf = ManagedFile(<your-file>, <your-resource>)
   mf.sync_to_resource()
   path = mf.get_remote_path()

Unless constructed with `ManagedFile(..., detect_nfs=False)`, ManagedFile
employs the following heuristic to check if a file is on NFS and if so, foregoes
the transfer and `get_remote_path()` just returns the local path (which is
identical to the remote path in this case):

  - check if GNU coreutils stat(1) with option --format exists on local and
    remote system
  - check if inode number, total size and birth/modification timestamps match
    on local and remote system

ProxyManager
------------
The proxymanager is used to open connections across proxies via an attribute in
the resource. This allows gated testing networks by always using the exporter as
an SSH gateway to proxy the connections using SSH Forwarding. Currently this is
used in the `SerialDriver` for proxy connections.

Usage:

.. code-block:: python

   from labgrid.util.proxy import proxymanager

   proxymanager.get_host_and_port(<resource>)


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

Run Tests
~~~~~~~~~

.. code-block:: bash

    $ tox -r

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

Remote Target Reservation
~~~~~~~~~~~~~~~~~~~~~~~~~

For integration with CI systems (like Jenkins), it would help if the CI job
could reserve and wait for a specific target.
This could be done by managing a list of waiting users in the coordinator and
notifying the current user on each invocation of labgrid-client that another
user is waiting.
The reservation should expire after some time if it is not used to lock the
target after it becomes available.

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

CommandProtocol Support for Background Processes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Currently the CommandProtocol does not support long running
processes well.
An implementation should start a new process,
return a handle and forbid running other processes in the foreground.
The handle can be used to retrieve output from a command.

SSH Tunneling for Remote Infrastructure
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Client and exporter require a direct HTTP(S) connection to the coordinator.
Also, the clients connect directly to the exporters via SSH.
However, often the clients are in an office network,
while exporters run in separate lab networks,
making it necessary to open holes in the firewall to
connect to the coordinator or from client to exporter.
In this case, it would be useful to use SSH as the authentication service
and then use tunneling to connect to the coordinator or
for the client to exporter connections.

Support for PDU-Daemon
~~~~~~~~~~~~~~~~~~~~~~

The LAVA project developed their own daemon for power switching, the `PDU Daemon
<https://https://staging.validation.linaro.org/static/docs/v2/pdudaemon.html>`_.
Add support for the daemon in the NetworkPowerDriver.
