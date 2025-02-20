Usage
=====

.. _remote-usage:

Remote Access
-------------

As described in :ref:`remote-resources-and-places`, one of labgrid's main
features is granting access to boards connected to other hosts transparent for
the client.
To get started with remote access, take a look at
:ref:`remote-getting-started`.

Place Scheduling
~~~~~~~~~~~~~~~~

When sharing places between developers or with CI jobs, it soon becomes
necessary to manage who can access which places.
Developers often just need any place which has one of a group of identical
devices, while CI jobs should wait until the necessary place is free instead of
failing.

To support these use-cases, the coordinator has support for reserving places by
using a tag filter and an optional priority.
First, the places have to be tagged with the relevant key-value pairs:

.. code-block:: bash

  $ labgrid-client -p board-1 set-tags board=imx6-foo
  $ labgrid-client -p board-2 set-tags board=imx6-foo
  $ labgrid-client -p board-3 set-tags board=imx8m-bar
  $ labgrid-client -v places
  Place 'board-1':
    tags: bar=baz, board=imx6-foo, jlu=2, rcz=1
    matches:
      rl-test/Testport1/NetworkSerialPort
  …
  Place 'board-2':
    tags: board=imx6-foo
    matches:
      rl-test/Testport2/NetworkSerialPort
  …
  Place 'board-3':
    tags: board=imx8m-bar
    matches:
      rl-test/Testport3/NetworkSerialPort
  …

Now, if you want to access any ``imx6-foo`` board, you could find that all are
already in use by someone else:

.. code-block:: bash

  $ labgrid-client who
  User     Host     Place    Changed
  rcz      dude     board-1  2019-08-06 12:14:38.446201
  jenkins  worker1  board-2  2019-08-06 12:52:44.762131

In this case, you can create a reservation.
You can specify any custom tags as part of the filter, as well as
``name=<place-name>`` to select only a specific place (even if it has no custom
tags).

.. code-block:: bash

  $ labgrid-client reserve board=imx6-foo
  Reservation 'SP37P5OQRU':
    owner: rettich/jlu
    token: SP37P5OQRU
    state: waiting
    filters:
      main: board=imx6-foo
    created: 2019-08-06 12:56:49.779982
    timeout: 2019-08-06 12:57:49.779983

As soon as any matching place becomes free, the reservation state will change
from ``waiting`` to ``allocated``.
Then, you can use the reservation token prefixed by ``+`` to refer to the
allocated place for locking and usage.
While a place is allocated for a reservation, only the owner of the reservation
can lock that place.


.. code-block:: bash

  $ labgrid-client wait SP37P5OQRU
  owner: rettich/jlu
  token: SP37P5OQRU
  state: waiting
  filters:
    main: board=imx6-foo
  created: 2019-08-06 12:56:49.779982
  timeout: 2019-08-06 12:58:14.900621
  …
  owner: rettich/jlu
  token: SP37P5OQRU
  state: allocated
  filters:
    main: board=imx6-foo
  allocations:
    main: board-2
  created: 2019-08-06 12:56:49.779982
  timeout: 2019-08-06 12:58:46.145851
  $ labgrid-client -p +SP37P5OQRU lock
  acquired place board-2
  $ labgrid-client reservations
  Reservation 'SP37P5OQRU':
    owner: rettich/jlu
    token: SP37P5OQRU
    state: acquired
    filters:
      main: board=imx6-foo
    allocations:
      main: board-2
    created: 2019-08-06 12:56:49.779982
    timeout: 2019-08-06 12:59:11.840780
  $ labgrid-client -p +SP37P5OQRU console

When using reservation in a CI job or to save some typing, the ``labgrid-client
reserve`` command supports a ``--shell`` command to print code for evaluating
in the shell.
This sets the ``LG_TOKEN`` environment variable, which is then automatically
used by ``wait`` and expanded via ``-p +``.

.. code-block:: bash

  $ eval `labgrid-client reserve --shell board=imx6-foo`
  $ echo $LG_TOKEN
  ZDMZJZNLBF
  $ labgrid-client wait
  owner: rettich/jlu
  token: ZDMZJZNLBF
  state: waiting
  filters:
    main: board=imx6-foo
  created: 2019-08-06 13:05:30.987072
  timeout: 2019-08-06 13:06:44.629736
  …
  owner: rettich/jlu
  token: ZDMZJZNLBF
  state: allocated
  filters:
    main: board=imx6-foo
  allocations:
    main: board-1
  created: 2019-08-06 13:05:30.987072
  timeout: 2019-08-06 13:06:56.196684
  $ labgrid-client -p + lock
  acquired place board-1
  $ labgrid-client -p + show
  Place 'board-1':
    tags: bar=baz, board=imx6-foo, jlu=2, rcz=1
    matches:
      rettich/Testport1/NetworkSerialPort
    acquired: rettich/jlu
    acquired resources:
    created: 2019-07-29 16:11:52.006269
    changed: 2019-08-06 13:06:09.667682
    reservation: ZDMZJZNLBF

Finally, to avoid calling the ``wait`` command explicitly, you can add
``--wait`` to the ``reserve`` command, so it waits until the reservation is
allocated before returning.

A reservation will time out after a short time, if it is neither refreshed nor
used by locked places.

Library
-------
labgrid can be used directly as a Python library, without the infrastructure
provided by the pytest plugin.

The labgrid library provides two ways to configure targets with resources and
drivers: either create the :any:`Target` directly or use :any:`Environment` to
load a configuration file.

.. note::
   On exit of your script/application, labgrid will call ``cleanup()`` on the
   targets using the python atexit module.

Targets
~~~~~~~

.. note::
   In most cases it is easier to :ref:`use a complete environment from a YAML
   file <usage_environments>` instead of manually creating and activating objects.
   Nevertheless, we explain this in the following to clarify the underlying concepts,
   and how to work with targets on a lower level, e.g. in strategies.

At the lower level, a :any:`Target` can be created directly:

.. doctest::

  >>> from labgrid import Target
  >>> t = Target('example')

Next, any required :any:`Resource` objects can be created, which each represent
a piece of hardware to be used with labgrid:

.. doctest::

  >>> from labgrid.resource import RawSerialPort
  >>> rsp = RawSerialPort(t, name=None, port='/dev/ttyUSB0')

.. note::
   Since we support multiple drivers of the same type, resources and drivers
   have a required ``name`` attribute. If you don't use multiple drivers of the
   same type, you can set the name to ``None``.

Further on, a :any:`Driver` encapsulates logic how to work with resources.
Drivers need to be created on the :any:`Target`:

.. doctest::

  >>> from labgrid.driver import SerialDriver
  >>> sd = SerialDriver(t, name=None)

As the :any:`SerialDriver` declares a binding to a :any:`SerialPort`, the target binds it
to the resource object created above:

.. doctest::

  >>> sd.port
  RawSerialPort(target=Target(name='example', env=None), name=None, state=<BindingState.bound: 1>, avail=True, port='/dev/ttyUSB0', speed=115200)
  >>> sd.port is rsp
  True

Driver Activation
^^^^^^^^^^^^^^^^^
Before a bound driver can be used, it needs to be activated.
During activation, the driver makes sure that all hardware represented by the
resources it is bound to can be used, and, if necessary, it acquires the
underlying hardware on the OS level.
For example, activating a :any:`SerialDriver` makes sure that the hardware
represented by its bound :any:`RawSerialPort` object (e.g. something like
``/dev/ttyUSB0``) is available, and that it can only be used labgrid and not by
other applications while the :any:`SerialDriver` is activated.

If we use a car analogy here, binding is the process of screwing the car parts
together, and activation is igniting the engine.

After activation, we can use the driver to do our work:

.. testsetup:: driver-activation

  from labgrid.resource import RawSerialPort
  from labgrid.driver import SerialDriver
  from labgrid import Target

  t = Target('example')
  rsp = RawSerialPort(t, name=None, port='/dev/ttyUSB0')
  sd = SerialDriver(t, name=None)
  sd.serial.open = Mock()
  sd.serial.write = Mock(return_value=4)

.. doctest:: driver-activation

  >>> t.activate(sd)
  >>> sd.write(b'test')
  4

If an underlying hardware resource is not available (or not available after a
certain timeout, depending on the driver), the activation step will raise an
exception, e.g.::

  >>> t.activate(sd)
  Traceback (most recent call last):
    File "/usr/lib/python3.8/site-packages/serial/serialposix.py", line 288, in open
      self.fd = os.open(self.portstr, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
  FileNotFoundError: [Errno 2] No such file or directory: '/dev/ttyUSB0'

Active drivers can be accessed by class (any :any:`Driver <labgrid.driver>` or
:any:`Protocol <labgrid.protocol>`) using some syntactic sugar:

.. doctest::

  >>> from labgrid import Target
  >>> from labgrid.driver.fake import FakeConsoleDriver
  >>> target = Target('main')
  >>> console = FakeConsoleDriver(target, 'console')
  >>> target.activate(console)
  >>> target[FakeConsoleDriver]
  FakeConsoleDriver(target=Target(name='main', env=None), name='console', state=<BindingState.active: 2>, txdelay=0.0)
  >>> target[FakeConsoleDriver, 'console']
  FakeConsoleDriver(target=Target(name='main', env=None), name='console', state=<BindingState.active: 2>, txdelay=0.0)

Driver Deactivation
^^^^^^^^^^^^^^^^^^^
Driver deactivation works in a similar manner:

.. testsetup:: driver-deactivation

  from labgrid import Target
  from labgrid.driver.fake import FakeConsoleDriver
  target = Target('main')
  console = FakeConsoleDriver(target, 'console')
  target.activate(console)

.. doctest:: driver-deactivation

  >>> target.deactivate(console)
  [FakeConsoleDriver(target=Target(name='main', env=None), name='console', state=<BindingState.bound: 1>, txdelay=0.0)]

Drivers need to be deactivated in the following cases:

* Some drivers have internal logic depending on the state of the target.
  For example, the :any:`ShellDriver` remembers whether it has already logged
  in to the shell.
  If the target reboots, e.g. through a hardware watchdog timeout,
  a power cycle, or by issuing a ``reboot`` command on the shell,
  the ShellDriver's internal state becomes outdated,
  and the ShellDriver needs to be deactivated and re-activated.

* One of the driver's bound resources is required by another driver which is to
  be activated.
  For example, the :any:`ShellDriver` and the :any:`BareboxDriver` both
  require access to a :any:`SerialPort` resource.
  If both drivers are bound to the same resource object, labgrid will
  automatically deactivate the BareboxDriver when activating the ShellDriver.

Target Cleanup
^^^^^^^^^^^^^^
After you are done with the target, optionally call the cleanup method on your
target. While labgrid registers an ``atexit`` handler to cleanup targets, this has
the advantage that exceptions can be handled by your application:

.. testsetup:: target-cleanup

  from labgrid import Target
  target = Target('main')

.. doctest:: target-cleanup

  >>> try:
  ...     target.cleanup()
  ... except Exception as e:
  ...     pass  # your code here

.. _usage_environments:

Environments
~~~~~~~~~~~~
In practice, it is often useful to separate the `Target` configuration from the
code which needs to control the board (such as a test case or installation
script).
For this use-case, labgrid can construct targets from a configuration file in
YAML format:

.. code-block:: yaml
  :name: example-env.yaml

  targets:
    example:
      resources:
        RawSerialPort:
          port: '/dev/ttyUSB0'
      drivers:
        SerialDriver: {}

To parse this configuration file, use the :any:`Environment` class:

.. doctest::

  >>> from labgrid import Environment
  >>> env = Environment('example-env.yaml')

Using :any:`Environment.get_target`, the configured `Targets` can be retrieved
by name.
Without an argument, `get_target` would default to 'main':

.. doctest::

  >>> t = env.get_target('example')

To access the target's console, the correct driver object can be found by using
:any:`Target.get_driver`:

.. testsetup:: get-driver

  from labgrid import Environment

  env = Environment('example-env.yaml')
  t = env.get_target('example')

  s = t.get_driver('SerialDriver', activate=False)
  s.serial.open = Mock()
  s.serial.write = Mock(return_value=4)

.. doctest:: get-driver

  >>> cp = t.get_driver('ConsoleProtocol')
  >>> cp
  SerialDriver(target=Target(name='example', env=Environment(config_file='example-env.yaml')), name=None, state=<BindingState.active: 2>, txdelay=0.0, timeout=3.0)
  >>> cp.write(b'test')
  4

When using the ``get_driver`` method, the driver is automatically activated.
The driver activation will also wait for unavailable resources when needed.

For more information on the environment configuration files and the usage of
multiple drivers, see :ref:`configuration:Environment Configuration`.

pytest Plugin
-------------
labgrid includes a `pytest <http://pytest.org>`_ plugin to simplify writing tests which
involve embedded boards.
The plugin is configured by providing an environment config file
(via the --lg-env pytest option, or the LG_ENV environment variable)
and automatically creates the targets described in the environment.

These `pytest fixtures <http://docs.pytest.org/en/latest/fixture.html>`_ are provided:

env (session scope)
  Used to access the :any:`Environment` object created from the configuration
  file.
  This is mostly used for defining custom fixtures at the test suite level.

target (session scope)
  Used to access the 'main' :any:`Target` defined in the configuration file.

strategy (session scope)
  Used to access the :any:`Strategy` configured in the 'main' :any:`Target`.

Command-Line Options
~~~~~~~~~~~~~~~~~~~~
The pytest plugin also supports the verbosity argument of pytest:

- ``-vv``: activates the step reporting feature, showing function parameters and/or results
- ``-vvv``: activates debug logging

This allows debugging during the writing of tests and inspection during test runs.

Other labgrid-related pytest plugin options are:

``--lg-env=LG_ENV`` (was ``--env-config=ENV_CONFIG``)
  Specify a labgrid environment config file.
  This is equivalent to labgrid-client's ``-c``/``--config``.

``--lg-coordinator=COORDINATOR_ADDRESS``
  Specify labgrid coordinator gRPC address as ``HOST[:PORT]``.
  Defaults to ``127.0.0.1:20408``.
  This is equivalent to labgrid-client's ``-x``/``--coordinator``.

``--lg-log=[path to logfiles]``
  Path to store console log file.
  If option is specified without path the current working directory is used.

``--lg-colored-steps``
  Previously enabled the ColoredStepReporter, which has been removed with the
  StepLogger introduction.
  Kept for compatibility reasons without effect.

``--lg-initial-state=STATE_NAME``
  Sets the Strategy's initial state.
  This is useful during development if the board is known to be in a defined
  state already.
  The Strategy used must implement the ``force()`` method.
  See the shipped :any:`ShellStrategy` for an example.

``pytest --help`` shows these options in a separate *labgrid* section.

Environment Variables
~~~~~~~~~~~~~~~~~~~~~

LG_ENV
^^^^^^
Behaves like ``LG_ENV`` for :doc:`labgrid-client <man/client>`.

LG_PROXY
^^^^^^^^
Specifies a SSH proxy host to be used for port forwards to access the
coordinator. Network resources made available by the exporter will prefer their
own proxy, and only fallback to LG_PROXY.

See also :ref:`overview-proxy-mechanism`.

Simple Example
~~~~~~~~~~~~~~

As a minimal example, we have a target connected via a USB serial converter
('/dev/ttyUSB0') and booted to the Linux shell.
The following environment config file (``shell-example.yaml``) describes how to
access this board:

.. code-block:: yaml
  :name: shell-example.yaml

  targets:
    main:
      resources:
        RawSerialPort:
          port: '/dev/ttyUSB0'
      drivers:
        SerialDriver: {}
        ShellDriver:
          prompt: 'root@[\w-]+:[^ ]+ '
          login_prompt: ' login: '
          username: 'root'

We then add the following test in a file called ``test_example.py``:

.. code-block:: python
  :name: test_shell.py

  def test_echo(target):
      command = target.get_driver('CommandProtocol')
      result = command.run_check('echo OK')
      assert 'OK' in result

To run this test, we simply execute pytest in the same directory with the
environment config:

.. testsetup:: pytest-example

  from labgrid.driver import SerialDriver, ShellDriver

  patch('serial.Serial').start()
  patch.object(
      SerialDriver,
      '_read',
      Mock(return_value=b'root@example:~ ')
  ).start()
  patch.object(
      ShellDriver,
      '_run',
      Mock(return_value=(['OK'], [], 0))
  ).start()

.. testcode:: pytest-example
  :hide:

  import pytest

  plugins = ['labgrid.pytestplugin']
  pytest.main(['--lg-env', 'shell-example.yaml', 'test_shell.py'], plugins)

.. testoutput:: pytest-example
  :hide:

  ... 1 passed...

.. code-block:: bash

  $ pytest --lg-env shell-example.yaml --verbose
  ============================= test session starts ==============================
  platform linux -- Python 3.5.3, pytest-3.0.6, py-1.4.32, pluggy-0.4.0
  …
  collected 1 items

  test_example.py::test_echo PASSED
  =========================== 1 passed in 0.51 seconds ===========================

pytest has automatically found the test case and executed it on the target.

Custom Fixture Example
~~~~~~~~~~~~~~~~~~~~~~
When writing many test cases which use the same driver, we can get rid of some
common code by wrapping the `CommandProtocol` in a fixture.
As pytest always executes the ``conftest.py`` file in the test suite directory,
we can define additional fixtures there:

.. code-block:: python
  :name: conftest_fixture.py

  import pytest

  @pytest.fixture(scope='session')
  def command(target):
      return target.get_driver('CommandProtocol')

With this fixture, we can simplify the ``test_example.py`` file to:

.. code-block:: python
  :name: test_custom_fixture.py

  def test_echo(command):
      result = command.run_check('echo OK')
      assert 'OK' in result

.. testcode:: pytest-example
  :hide:

  import pytest

  plugins = ['labgrid.pytestplugin', 'conftest_fixture']
  pytest.main(['--lg-env', 'shell-example.yaml', 'test_custom_fixture.py'], plugins)

.. testoutput:: pytest-example
  :hide:

  ... 1 passed...

Strategy Fixture Example
~~~~~~~~~~~~~~~~~~~~~~~~
When using a :any:`Strategy` to transition the target between states, it is
useful to define a function scope fixture per state in ``conftest.py``:

.. code-block:: python

  import pytest

  @pytest.fixture(scope='function')
  def switch_off(strategy, capsys):
      with capsys.disabled():
          strategy.transition('off')

  @pytest.fixture(scope='function')
  def bootloader_command(target, strategy, capsys):
      with capsys.disabled():
          strategy.transition('barebox')
      return target.get_active_driver('CommandProtocol')

  @pytest.fixture(scope='function')
  def shell_command(target, strategy, capsys):
      with capsys.disabled():
          strategy.transition('shell')
      return target.get_active_driver('CommandProtocol')

.. note::
  The ``capsys.disabled()`` context manager is only needed when using the
  :any:`ManualPowerDriver`, as it will not be able to access the console
  otherwise.
  See the corresponding `pytest documentation for details
  <http://doc.pytest.org/en/latest/capture.html#accessing-captured-output-from-a-test-function>`_.

With the fixtures defined above, switching between bootloader and Linux shells
is easy:

.. code-block:: python

  def test_barebox_initial(bootloader_command):
      stdout = bootloader_command.run_check('version')
      assert 'barebox' in '\n'.join(stdout)

  def test_shell(shell_command):
      stdout = shell_command.run_check('cat /proc/version')
      assert 'Linux' in stdout[0]

  def test_barebox_after_reboot(bootloader_command):
      bootloader_command.run_check('true')

.. note::
  The `bootloader_command` and `shell_command` fixtures use
  :any:`Target.get_active_driver` to get the currently active `CommandProtocol`
  driver (either :any:`BareboxDriver` or :any:`ShellDriver`).
  Activation and deactivation of drivers is handled by the
  :any:`BareboxStrategy` in this example.

The `Strategy` needs additional drivers to control the target.
Adapt the following environment config file (``strategy-example.yaml``) to your
setup:

.. code-block:: yaml

  targets:
    main:
      resources:
        RawSerialPort:
          port: '/dev/ttyUSB0'
      drivers:
        ManualPowerDriver:
          name: 'example-board'
        SerialDriver: {}
        BareboxDriver:
          prompt: 'barebox@[^:]+:[^ ]+ '
        ShellDriver:
          prompt: 'root@[\w-]+:[^ ]+ '
          login_prompt: ' login: '
          username: 'root'
        BareboxStrategy: {}

For this example, you should get a report similar to this:

.. code-block:: bash

  $ pytest --lg-env strategy-example.yaml -v --capture=no
  ============================= test session starts ==============================
  platform linux -- Python 3.5.3, pytest-3.0.6, py-1.4.32, pluggy-0.4.0
  …
  collected 3 items

  test_strategy.py::test_barebox_initial
  main: CYCLE the target example-board and press enter
  PASSED
  test_strategy.py::test_shell PASSED
  test_strategy.py::test_barebox_after_reboot
  main: CYCLE the target example-board and press enter
  PASSED

  ========================== 3 passed in 29.77 seconds ===========================

Feature Flags
~~~~~~~~~~~~~
labgrid includes support for feature flags on a global and target scope.
Adding a ``@pytest.mark.lg_feature`` decorator to a test ensures it is only
executed if the desired feature is available:

.. code-block:: python
   :name: test_feature_flags.py

   import pytest

   @pytest.mark.lg_feature("camera")
   def test_camera(target):
      pass

Here's an example environment configuration:

.. code-block:: yaml
  :name: feature-flag-env.yaml

  targets:
    main:
      features:
        - camera
      resources: {}
      drivers: {}

.. testcode:: pytest-example
  :hide:

  import pytest

  plugins = ['labgrid.pytestplugin']
  pytest.main(['--lg-env', 'feature-flag-env.yaml', 'test_feature_flags.py'], plugins)

.. testoutput:: pytest-example
  :hide:

  ... 1 passed...

This would run the above test, however the following configuration would skip the
test because of the missing feature:

.. code-block:: yaml
  :name: feature-flag-skip-env.yaml

  targets:
    main:
      features:
        - console
      resources: {}
      drivers: {}

.. testcode:: pytest-example
  :hide:

  import pytest

  plugins = ['labgrid.pytestplugin']
  pytest.main(['--lg-env', 'feature-flag-skip-env.yaml', 'test_feature_flags.py'], plugins)

.. testoutput:: pytest-example
  :hide:

  ... 1 skipped...

pytest will record the missing feature as the skip reason.

For tests with multiple required features, pass them as a list to pytest:

.. code-block:: python
   :name: test_feature_flags_global.py

   import pytest

   @pytest.mark.lg_feature(["camera", "console"])
   def test_camera(target):
      pass

Features do not have to be set per target, they can also be set via the global
features key:

.. code-block:: yaml
  :name: feature-flag-global-env.yaml

  features:
    - camera
  targets:
    main:
      features:
        - console
      resources: {}
      drivers: {}

.. testcode:: pytest-example
  :hide:

  import pytest

  plugins = ['labgrid.pytestplugin']
  pytest.main(['--lg-env', 'feature-flag-global-env.yaml', 'test_feature_flags_global.py'],
              plugins)

.. testoutput:: pytest-example
  :hide:

  ... 1 passed...

This YAML configuration would combine both the global and the target features.


Test Reports
~~~~~~~~~~~~

pytest-html
^^^^^^^^^^^
With the `pytest-html plugin <https://pypi.python.org/pypi/pytest-html>`_, the
test results can be converted directly to a single-page HTML report:

.. code-block:: bash

  $ pip install pytest-html
  $ pytest --lg-env shell-example.yaml --html=report.html

JUnit XML
^^^^^^^^^
JUnit XML reports can be generated directly by pytest and are especially useful for
use in CI systems such as `Jenkins <https://jenkins.io/>`_ with the `JUnit
Plugin <https://wiki.jenkins-ci.org/display/JENKINS/JUnit+Plugin>`_.

They can also be converted to other formats, such as HTML with `junit2html tool
<https://pypi.python.org/pypi/junit2html>`_:

.. code-block:: bash

  $ pip install junit2html
  $ pytest --lg-env shell-example.yaml --junit-xml=report.xml
  $ junit2html report.xml


labgrid adds additional xml properties to a test run, these are:

- ENV_CONFIG: Name of the configuration file
- TARGETS: List of target names
- TARGET_{NAME}_REMOTE: optional, if the target uses a RemotePlace
  resource, its name is recorded here
- PATH_{NAME}: optional, labgrid records the name and path
- PATH_{NAME}_GIT_COMMIT: optional, labgrid tries to record git sha1 values for every
  path 
- IMAGE_{NAME}: optional, labgrid records the name and path to the image 
- IMAGE_{NAME}_GIT_COMMIT: optional, labgrid tries to record git sha1 values for every
  image 

Command-Line
------------

labgrid contains some command line tools which are used for remote access to
resources.
See :doc:`man/client`, :doc:`man/device-config` and :doc:`man/exporter` for
more information.

Advanced CLI features
~~~~~~~~~~~~~~~~~~~~~

This section of the manual describes advanced features that are supported by the
labgrid client CLI.

Sharing a place with a co-worker
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Labgrid client allows multiple people to access the same shared place,
even though locks can only be acquired by one person. To allow a coworker to use
a place use the ``allow`` command of labgrid client in conjunction with the
coworkers ``user`` and ``hostname``. As an example, with a places named
``example``, a user name ``john`` and a host named ``sirius``, the command looks
like this:

.. code-block:: bash

  $ labgrid-client -p example allow sirius/john

To remove the allow it is currently necessary to unlock and lock the place.
