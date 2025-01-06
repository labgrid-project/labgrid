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

``--lg-target==TARGET_NAME``
  Sets the target to use for the test. This is optional since the target can be
  provided in the configuration file. Specify this option if you have an
  environment containing multiple boards and you want to select which one to
  use.

``--lg-var <name> <value>``
  Allows setting a variable to a particular value. This is useful for complex
  strategies which can be controlled by variables. This option can be specified
  multiple types as needed.

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
          prompt: 'root@\w+:[^ ]+ '
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
          prompt: 'root@\w+:[^ ]+ '
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

U-Boot Integration
------------------

.. note::
   See status_ for current status and development branches.

Most ARM boards (and some others) use U-Boot as their bootloader. Labgrid
provides various features to help with development and testing on these boards.
Together these features allow interactive use of Labgrid to build U-Boot from
source, write it to a board and boot it. Support is provided for U-Boot's pytest
and Gitlab setup.

This section describes the various features which contribute to the overall
functionality. The names of contributed scripts (in *contrib/u-boot*) are shown
in brackets.

Compatibility
~~~~~~~~~~~~~

This integration mostly does not require special support in U-Boot's pytest
system, but it does benefit from it. Specifically, newer U-Boot versions
understand the Labgrid concept of a role (corresponding to --board-identity in
test.py), which simplifies the integration.

Also, with newer U-Boot versions, the following features are available:

- Support for pytest with boards needing multiple U-Boot builds, e.g. Beagleplay
- A special 'Lab mode' lets Labgrid handle detecting the U-Boot banner and
  stopping autoboot, thus avoiding SPL banner counting and other complexities
  in test.py
- Dead connections are detected quickly and cause testing to halt, thus avoiding
  hour-long delays when a board in the lab is just broken
- The double echo on start-up is resolved, which can cause pytest to fail,
  thinking that U-Boot is not responding. For example, when pytest sends
  "version", the first three characters may be echoed by the PTY before Labgrid
  puts it into no-echo mode; when it finally does, U-Boot echos "version" and
  the result is that pytest sees "verversion" and fails.

Interactive use
~~~~~~~~~~~~~~~

Labgrid provides a 'console' command which can be used to connect to a board.
The :ref:`UBootStrategyInfo` driver provides a way to power cycle (or reset)
the board so that U-Boot starts. It also provides two useful states:

- `start` which starts up U-Boot and lets it boot (*ub-int*)
- `uboot` which starts up U-Boot and stops it at the CLI prompt (*ub-cli*)

Both of these are useful in development.

Building U-Boot
~~~~~~~~~~~~~~~

Labgrid intentionally
`doesn't include <https://github.com/labgrid-project/labgrid/issues/1068>`_
build functionality as usually the software-under-test already comes with a
build system and it wants to test the artifacts as built by the "real" build
system.

U-Boot is no exception and it provides the
`buildman <https://docs.u-boot.org/en/latest/build/buildman.html>`_ for this
purpose.

Still, for interactive use some sort of build is needed. The
:ref:`UBootProviderInfo` provides an interface to buildman and a way of dealing
with board-specific binary blobs. The buildman tool works automatically provided
that you have set it up with suitable toolchains. See
`buildman <https://docs.u-boot.org/en/latest/build/buildman.html>`_ for more
information.

Writing U-Boot
~~~~~~~~~~~~~~

Writing U-Boot to a board can be complicated, because each SoC uses its own
means of booting. The other problem is that special lab hardware is generally
needed to update the boot device, e.g.
`SD-wire <https://wiki.tizen.org/SD_MUX>`_.

Fortunately Labgrid provides the means for manipulating the lab hardware. All
that is needed is a driver which understands where to write images, which files
to use and the sequence to use in each case. The :ref:`UBootWriterInfo` driver
handles this. It picks out the necessary files from a build directory and writes
them to the selected boot media, or sends them using the SoC-specific bootrom.
Combined with :ref:`UBootStrategyInfo` it provides automated updating of U-Boot
on suported SoCs regardless of the lab setup.

Run labgrid tests
~~~~~~~~~~~~~~~~~

Labgrid provides integration with pytest. As part of the U-Boot integration, a
conftest.py file is provided which can build and smoke-test U-Boot on a board
(*ub-smoke*).

Run U-Boot tests
~~~~~~~~~~~~~~~~~

It is also possible to run the U-Boot tests (*ub-pyt*). To do this you will need
to set up Labgrid integration with the
`U-Boot test hooks <https://source.denx.de/u-boot/u-boot-test-hooks>`_.
To do this, create the directory `u-boot-test-hooks/bin/$hostname` and add an
executable file called `common.labgrid` which sets the crossbar and environment
information:

.. code-block:: bash

    export LG_CROSSBAR="ws://kea:20408/ws"
    export LG_ENV="/path/to/env.cfg"

    flash_impl=none
    reset_impl=none
    console_impl=labgrid
    release_impl=labgrid

The last four lines tell the hooks to use labgrid.

Then create another executable file (in the same directory) called 'conf.all',
containing:

.. code-block:: bash

    . "${bin_dir}/${hostname}/common-labgrid"

Bisecting
~~~~~~~~~

It is possible to use the *ub-pyt* or *ub-smoke* scripts with `git bisect run`
to bisect a problem on a particular board. However there is a slightly more
powerful script which supports applying a commit each time (*ub-bisect*).

Setting up pytest
~~~~~~~~~~~~~~~~~

To set up the U-Boot pytest integration:

#. Copy the `contrib/u-boot` directory to somewhere suitable and add it to your
   path. For example:

.. code-block:: bash

      cp -a contrib/u-boot ~/bin/u-boot
      echo 'PATH="$PATH:~/bin/u-boot"' >> ~/.bashrc

#. Edit the `lg-env` file to set the lab parameters according to your setup.
#. Start a new terminal, or login again, so the path updates. You can now use
   the scripts as documented below.

Note that the ub-pyt scripts must be run from the U-Boot source directory, since
it uses files in the test/py directory.

Script usage
~~~~~~~~~~~~

The scripts are intended to run inside the U-Boot source directory, alongside
normal U-Boot development. For example::

    ub-int play

builds U-Boot for 'play' (which must be defined in your environment file), loads
it onto the board and starts an interactive session. An internal terminal is
used by default, use press Ctrl-] twice (quickly) to exit.

The U-Boot 'strategy' within Labgrid handles most of the complexity. The scripts
are really just an interface to labgrid-client. When bootstrapping U-Boot onto a
board, some directories are needed in your environment::

    paths:
      uboot_build_base: "/tmp/b"
      uboot_workdirs: "/tmp/b/workdirs"
      uboot_source: "/home/sglass/dev/u-boot"

    tools:
      buildman: "buildman"
      servod: "/tools/standalone-hdctools/servod"
      dut-control: "/tools/standalone-hdctools/dut-control"

Builds are stored in a target subdirectory of uboot_build_base, so the target
'play' would be built in /tmp/b/play in this example. Each board has its own
directory so that incremental building works correctly and the existing build
can be reused. A workdir is created (here in /tmp/b/workdirs/play) if you
specify a patch to add to the build. The last two tools relate to the ChromiumOS
Servo board.

The uboot_source directory points to the U-Boot source code which is built.

The integration uses the concept of a role to encapsule both the target being
used and the environment attached to it. This allows the same target  to be
mentioned twice in the environment, each with different settings. For example,
a target which can support two differents U-Boot boards (such as Samus, which
has chromebook_samus and chromebook_samus_tpl) can be invoked with either.

Various flags are available in the different tools - use '-h' to get help.

The normal case (with no flags) is to build, bootstrap, power on/reset and
connect to the board. This uses UBootStrategy 'start' to get things running,
then selects 'off' when done.

For example::

  $ ub-int play
  Building U-Boot in sourcedir for am62x_beagleplay_a53
  Building U-Boot in sourcedir for am62x_beagleplay_r5
  Bootstrapping U-Boot from dir /tmp/b/am62x_beagleplay_a53 /tmp/b/am62x_beagleplay_r5
  Writing U-Boot using method ti,am625

  U-Boot SPL 2024.10-rc3-00327-g428ab736ed5a (Aug 28 2024 - 06:30:35 -0600)
  SYSFW ABI: 3.1 (firmware rev 0x0009 '9.2.8--v09.02.08 (Kool Koala)')
  Changed A53 CPU frequency to 1250000000Hz (T grade) in DT
  ...
  Ctrl-] Ctrl-]
  (board powers off)

You can use -R to avoid any building/bootstrapping or even resetting the board:
it just connects to the running board, assuming it is powering out. The -T
option handles power and reset, but does not build or bootstrap, so normally the
board will start up the version of U-Boot already installed. Use -B to skip the
build but do the bootstrap and power/reset. The existing build will be
bootstrapped onto the board. The -d option is useful here, since it lets you
specify the build directory to use.

To perform a clean build using 'make mrproper', use the -c flag. Normally,
bootstrapping uses the device's storage, e.g. using an SD-Wire mux, but the -s
option sends U-Boot over USB instead. For this to work, the board needs a USB
connection and a BootstrapProtocol driver (e.g. MXSUSBDriver).

Use the -l option to log the console output to a file. Since U-Boot normally
echoes its input, this should provide the full session log.

To see a bit more of what is going on under the hood, the -v (verbose) and
-d (debug) flags can be useful.

The above flags can be used when running tests as well, for example::

    ub-pyt -B play help or bdinfo

Note that when testing U-Boot versions without the pytest enhancements, some
options may not be available, e.g.

Gitlab Integration
~~~~~~~~~~~~~~~~~~

U-Boot uses `Gitlab <https://gitlab.com>`_ as the basis for its Continuous
Integration (CI) system (`U-Boot instance <https://source.denx.de/u-boot>`_).
It is possible to set up your own lab which integrates with Gitlab, with your
own Git lab 'runner' which can control Labgrid. This allows pushing branches to
Gitlab and running tests on real hardware, similarly to how QEMU is used in
Gitlab.

To set this up:

#. Install `gitlab-runner` using these
   `instructions <https://docs.gitlab.com/runner/install/linux-repository.html>`_.

#. Register a
   `new runner <https://docs.gitlab.com/ee/tutorials/create_register_first_runner>`_
   following the instructions using your custodian CI settings (i.e. do this at
   `https://source.denx.de`).

   Select Linux and with tags set to `lab`. Click `Create runner` and use the
   command line to register the runner. Use `<hostname>-lab` (for example
   `kea-lab`) as your host name and select `shell` as the executor:

   .. code-block:: console

       $ gitlab-runner register  --url https://source.denx.de  --token glrt-xxx
       Enter the GitLab instance URL (for example, https://gitlab.com/):
       [https://source.denx.de]:
       Verifying runner... is valid                        runner=yyy
       Enter a name for the runner. This is stored only in the local config.toml file:
       [<hostname>]: <hostname>-lab
       Enter an executor: ssh, parallels, docker-windows, docker+machine, kubernetes, instance, custom, shell, virtualbox, docker, docker-autoscaler:
       shell
       Runner registered successfully. Feel free to start it, but if it's running already the config should be automatically reloaded!

#. Edit the resulting `/etc/gitlab-runner/config.toml` file to allow more than
   one job at a time by adding 'concurrent = x' where x is the number of jobs.
   Here we use concurrent = 8 (this is just an example; don't replace your file
   with this):

   .. code-block:: toml

       concurrent = 8
       check_interval = 0
       shutdown_timeout = 0

       [session_server]
         session_timeout = 1800

       [[runners]]
         name = "ellesmere-lab"
         url = "https://source.denx.de"
         id = 130
         token = "..."
         token_obtained_at = 2024-05-15T20:41:29Z
         token_expires_at = 0001-01-01T00:00:00Z
         executor = "shell"
         [runners.custom_build_dir]

#. Gitlab will run tests as the 'gitlab-runner' user. Make sure your labgrid
   installation is installed such that it is visible to that user. One way is:

   .. code-block:: bash

       sudo su - gitlab-runner
       cd /path/to/labgrid
       pip install .

#. Add the following to U-Boot's `.gitlab-ci.yml`, adjusting the variables as
   needed. For trying it out initially you might want to disable all the other
   rules by changing `when: always` to `when: never`:

   .. code-block:: yaml

       .lab_template: &lab_dfn
         stage: lab
         tags: [ 'lab' ]
         script:
           # Environment:
           #   SRC  - source tree
           #   ROOT - directory above that
           #   OUT  - output directory for builds
           - export SRC="$(pwd)"
           - ROOT="$(dirname ${SRC})"
           - export OUT="${ROOT}/out"
           - export PATH=$PATH:~/bin
           - export PATH=$PATH:/vid/software/devel/ubtest/u-boot-test-hooks/bin

           # Load it on the device
           - ret=0
           - echo "board ${BOARD} id ${ID}"
           - ${SRC}/test/py/test.py -B "${BOARD}" --id ${ID} --configure
               --build-dir "${OUT}/current/${BOARD}" -k "not bootstd"|| ret=$?
           - if [[ $ret -ne 0 ]]; then
               exit $ret;
             fi

       rpi3:
         variables:
           BOARD: rpi_3_32b     ## This is a U-Boot board name
           ID: rpi3             ## This is the corresponding role/target
         <<: *lab_dfn

#. Commit your changes and push to your custodian tree. This example shows the
   driver model tree at a remote called 'dm':

   .. code-block:: bash

       $ git remote -v |grep dm
       dm       git@source.denx.de:u-boot/custodians/u-boot-dm.git (fetch)
       dm       git@source.denx.de:u-boot/custodians/u-boot-dm.git (push)
       $ git push dm HEAD:try

#. Navigate to the pipelines and you should see your tests running. You can
   debug things from there, e.g. using the `ub-int` or `ub-pyt` scripts on an
   individual board. An example may be visible
   `here <https://source.denx.de/u-boot/custodians/u-boot-dm/-/pipelines/20769>`_.

Scripts
~~~~~~~

Various scripts are provided in the `contrib/` directory, specifically targeted
at U-Boot testing and development.

.. include:: ../contrib/u-boot/index.rst


.. _status:

U-Boot Integration Status
~~~~~~~~~~~~~~~~~~~~~~~~~

Date: May '24
Overall status: Ready for early testing

Required pieces:

- `Labgrid WIP PR <https://github.com/sjg20/labgrid/tree/u-boot-integration>`_
- `U-Boot test hooks branch <https://github.com/sjg20/uboot-test-hooks/tree/labgrid>`_
- `U-Boot branch <https://github.com/sjg20/u-boot/tree/labgrid>`_ (needed for
  U-Boot pytest integration)

Testing has been very limited, basically a set of 21 boards, including sunxi,
rpi, RK3399, ODroid-C4, pine64, Orange Pi PC, various Chromebooks and Intel
Minnowboard Max.

Some U-Boot pytests fails on some hardware:
- TPM tests fail on boards with a TPM
- test_log_format fails on several (perhaps all?) boards

There are likely many other problems.
