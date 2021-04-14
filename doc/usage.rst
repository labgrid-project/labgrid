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

Creating and Configuring Targets
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The labgrid library provides two ways to configure targets with resources and
drivers: either create the :any:`Target` directly or use :any:`Environment` to
load a configuration file.

.. note::
   On exit of your script/application, labgrid will call ``cleanup()`` on the
   targets using the python atexit module.

Targets
^^^^^^^
At the lower level, a :any:`Target` can be created directly::

  >>> from labgrid import Target
  >>> t = Target('example')

Next, the required :any:`Resources <Resource>` can be created::

  >>> from labgrid.resource import RawSerialPort
  >>> rsp = RawSerialPort(t, name=None, port='/dev/ttyUSB0')

.. note::
   Since we support multiple drivers of the same type, resources and drivers
   have a required name attribute. If you don't require support for this
   functionality set the name to `None`.

Then, a :any:`Driver` needs to be created on the `Target`::

  >>> from labgrid.driver import SerialDriver
  >>> sd = SerialDriver(t, name=None)


As the `SerialDriver` declares a binding to a SerialPort, the target binds it
to the resource created above::

  >>> sd.port
  RawSerialPort(target=Target(name='example', env=None), name=None, state=<BindingState.bound: 1>, avail=True, port='/dev/ttyUSB0', speed=115200)
  >>> sd.port is rsp
  True

Before the driver can be used, it needs to be activated::

  >>> t.activate(sd)
  >>> sd.write(b'test')

Active drivers can be accessed by class (any `Driver` or `Protocol`) using some
syntactic sugar::

  >>> target = Target('main')
  >>> console = FakeConsoleDriver(target, 'console')
  >>> target.activate(console)
  >>> target[FakeConsoleDriver]
  FakeConsoleDriver(target=Target(name='main', …), name='console', …)
  >>> target[FakeConsoleDriver, 'console']
  FakeConsoleDriver(target=Target(name='main', …), name='console', …)

After you are done with the target, optionally call the cleanup method on your
target. While labgrid registers an atexit handler to cleanup targets, this has
the advantage that exceptions can be handled by your application:::

  >>> try:
  >>>     target.cleanup()
  >>> except Exception as e:
  >>>     <your code here>

Environments
^^^^^^^^^^^^
In practice, is is often useful to separate the `Target` configuration from the
code which needs to control the board (such as a test case or installation
script).
For this use-case, labgrid can construct targets from a configuration file in
YAML format:

.. code-block:: yaml

  targets:
    example:
      resources:
        RawSerialPort:
          port: '/dev/ttyUSB0'
      drivers:
        SerialDriver: {}

To parse this configuration file, use the :any:`Environment` class::

  >>> from labgrid import Environment
  >>> env = Environment('example-env.yaml')

Using :any:`Environment.get_target`, the configured `Targets` can be retrieved
by name.
Without an argument, `get_target` would default to 'main'::

  >>> t = env.get_target('example')

To access the target's console, the correct driver object can be found by using
:any:`Target.get_driver`::

  >>> from labgrid.protocol import ConsoleProtocol
  >>> cp = t.get_driver(ConsoleProtocol)
  >>> cp
  SerialDriver(target=Target(name='example', env=Environment(config_file='example.yaml')), name=None, state=<BindingState.active: 2>, txdelay=0.0)
  >>> cp.write(b'test')

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

Two `pytest fixtures <http://docs.pytest.org/en/latest/fixture.html>`_ are provided:

env (session scope)
  Used to access the :any:`Environment` object created from the configuration
  file.
  This is mostly used for defining custom fixtures at the test suite level.

target (session scope)
  Used to access the 'main' :any:`Target` defined in the configuration file.

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

``--lg-coordinator=CROSSBAR_URL``
  Specify labgrid coordinator websocket URL.
  Defaults to ``ws://127.0.0.1:20408/ws``.
  This is equivalent to labgrid-client's ``-x``/``--crossbar``.

``--lg-log=[path to logfiles]``
  Path to store console log file.
  If option is specified without path the current working directory is used.

``--lg-colored-steps``
  Enables the ColoredStepReporter.
  Different events have different colors.
  The more colorful, the more important.
  In order to make less important output "blend into the background" different
  color schemes are available.
  See :ref:`LG_COLOR_SCHEME <usage-lgcolorscheme>`.

``pytest --help`` shows these options in a separate *labgrid* section.

Environment Variables
~~~~~~~~~~~~~~~~~~~~~

LG_ENV
^^^^^^
Behaves like ``LG_ENV`` for :doc:`labgrid-client <man/client>`.

.. _usage-lgcolorscheme:

LG_COLOR_SCHEME
^^^^^^^^^^^^^^^
Influences the color scheme used for the Colored Step Reporter.
``dark`` is meant for dark terminal background.
``light`` is optimized for light terminal background.
``dark-256color`` and ``light-256color`` are respective variants for terminals
that support 256 colors.
By default, ``dark`` or ``dark-256color`` (depending on the terminal) are used.

Takes effect only when used with ``--lg-colored-steps``.

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

We then add the following test in a file called ``test_example.py``::

  from labgrid.protocol import CommandProtocol

  def test_echo(target):
      command = target.get_driver(CommandProtocol)
      result = command.run_check('echo OK')
      assert 'OK' in result

To run this test, we simply execute pytest in the same directory with the
environment config:

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
we can define additional fixtures there::

  import pytest

  from labgrid.protocol import CommandProtocol

  @pytest.fixture(scope='session')
  def command(target):
      return target.get_driver(CommandProtocol)

With this fixture, we can simplify the ``test_example.py`` file to::

  def test_echo(command):
      result = command.run_check('echo OK')
      assert 'OK' in result

Strategy Fixture Example
~~~~~~~~~~~~~~~~~~~~~~~~
When using a :any:`Strategy` to transition the target between states, it is
useful to define a function scope fixture per state in ``conftest.py``::

  import pytest

  from labgrid.protocol import CommandProtocol
  from labgrid.strategy import BareboxStrategy

  @pytest.fixture(scope='session')
  def strategy(target):
      try:
          return target.get_driver(BareboxStrategy)
      except NoDriverFoundError:
          pytest.skip("strategy not found")

  @pytest.fixture(scope='function')
  def switch_off(target, strategy, capsys):
      with capsys.disabled():
          strategy.transition('off')

  @pytest.fixture(scope='function')
  def bootloader_command(target, strategy, capsys):
      with capsys.disabled():
          strategy.transition('barebox')
      return target.get_active_driver(CommandProtocol)

  @pytest.fixture(scope='function')
  def shell_command(target, strategy, capsys):
      with capsys.disabled():
          strategy.transition('shell')
      return target.get_active_driver(CommandProtocol)

.. note::
  The ``capsys.disabled()`` context manager is only needed when using the
  :any:`ManualPowerDriver`, as it will not be able to access the console
  otherwise.
  See the corresponding `pytest documentation for details
  <http://doc.pytest.org/en/latest/capture.html#accessing-captured-output-from-a-test-function>`_.

With the fixtures defined above, switching between bootloader and Linux shells
is easy::

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

  $ pytest --lg-env strategy-example.yaml -v
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
executed if the desired feature is available::

   import pytest

   @pytest.mark.lg_feature("camera")
   def test_camera(target):
      [...]

Here's an example environment configuration:

.. code-block:: yaml

  targets:
    main:
      features:
        - camera
      resources: {}
      drivers: {}

This would run the above test, however the following configuration would skip the
test because of the missing feature:

.. code-block:: yaml

  targets:
    main:
      features:
        - console
      resources: {}
      drivers: {}

pytest will record the missing feature as the skip reason.

For tests with multiple required features, pass them as a list to pytest::

   import pytest

   @pytest.mark.lg_feature(["camera", "console"])
   def test_camera(target):
      [...]

Features do not have to be set per target, they can also be set via the global
features key:

.. code-block:: yaml

  features:
    - camera
  targets:
    main:
      features:
        - console
      resources: {}
      drivers: {}

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
