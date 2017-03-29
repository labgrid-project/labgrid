Usage
=====

Library
-------
Labgrid can be used directly as a Python library, without the infrastructure
provided by the pytest plugin.

Creating and Configuring Targets
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The labgrid library provides to ways to configure targets with resources and
drivers: either create the :any:`Target` directly or use :any:`Environment` to
load a configuration file.

Targets
^^^^^^^
At the lower level, a :any:`Target` can be created directly::

  >>> from labgrid import Target
  >>> t = Target('example')

Next, the required :any:`Resources <Resource>` can be created::

  >>> from labgrid.resource import RawSerialPort
  >>> rsp = RawSerialPort(t, port='/dev/ttyUSB0')

Then, a :any:`Driver` needs to be created on the `Target`::

  >>> from labgrid.driver import SerialDriver
  >>> sd = SerialDriver(t)

As the `SerialDriver` declares a binding to a SerialPort, the target binds it
to the resource created above::

  >>> sd.port
  RawSerialPort(target=Target(name='example', env=None), state=<BindingState.active: 2>, avail=True, port='/dev/ttyUSB0', speed=115200)
  >>> sd.port is rsp
  True

Before the driver can be used, it needs to be activated::

  >>> t.activate(sd)
  >>> sd.write(b'test')

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
  SerialDriver(target=Target(name='example', env=Environment(config_file='example.yaml')), state=<BindingState.active: 2>)
  >>> cp.write(b'test')

In when using the ``get_driver`` method, the driver is automatically activated.
The driver activation will also wait for unavailable resources when needed.

pytest Plugin
-------------
Labgrid include a `pytest <http://pytest.org>`_ plugin to simplify writing tests which
involve embedded boards.
The plugin is configured by providing an environment config file (via the
--env-config pytest option) and automatically create the targets described in
the environment.

Two `pytest fixtures <http://docs.pytest.org/en/latest/fixture.html>`_ are provided:

env (session scope)
  Used to access the :any:`Environment` object create from the configuration
  file.
  This is mostly used for defining custom fixtures at the test suite level.

target (session scope)
  Used to access the 'main' :any:`Target` defined in the configure file.

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
      command = t.get_driver(CommandProtocol)
      result = command.run_check('echo OK')
      assert 'OK' in result

To run this test, we simply execute pytest in the same directory with the
environment config:

.. code-block:: bash

  $ pytest --env-config shell-example.yaml --verbose
  ============================= test session starts ==============================
  platform linux -- Python 3.5.3, pytest-3.0.6, py-1.4.32, pluggy-0.4.0
  …
  collected 1 items

  test_example.py::test_echo PASSED
  =========================== 1 passed in 0.51 seconds ===========================

pytest automatically found the test case and executed it on the target.

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

Stategy Fixtures Example
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
  def in_bootloader(strategy, capsys):
      with capsys.disabled():
          strategy.transition("barebox")

  @pytest.fixture(scope='function')
  def in_shell(strategy, capsys):
      with capsys.disabled():
          strategy.transition("shell")

  @pytest.fixture(scope='function')
  def active_command(target):
      return target.get_active_driver(CommandProtocol)

.. note::
  The ``capsys.disabled()`` context manager is only needed when using the
  :any:`ManualPowerDriver`, as it will not be able to access the console
  otherwise.
  See the corresponding `pytest documentation for details
  <http://doc.pytest.org/en/latest/capture.html#accessing-captured-output-from-a-test-function>`_.

With the fixtures define above, switching between bootloader and linux shells
is easy::

  from labgrid.driver import BareboxDriver, ShellDriver

  def test_barebox_initial(active_command, in_bootloader):
      stdout = active_command.run_check('version')
      assert 'barebox' in '\n'.join(stdout)

  def test_shell(active_command, in_shell):
      stdout = active_command.run_check('cat /proc/version')
      assert 'Linux' in stdout[0]

  def test_barebox_after_reboot(active_command, in_bootloader):
      command = active_command.get_driver(BareboxDriver)
      command.run_check('true')

.. note::
  The `active_command` fixture uses :any:`Target.get_active_driver` to get the
  currently active `CommandProtocol` driver (either :any:`BareboxDriver` or
  :any:`ShellDriver`).
  Activation and deactivation of drivers is handled by the
  :any:`BareboxStrategy` in this example.

Test Reports
~~~~~~~~~~~~

pytest-html
^^^^^^^^^^^
With the `pytest-html plugin <https://pypi.python.org/pypi/pytest-html>`_, the
test results can be converted directly to a single-page HTML report:

.. code-block:: bash

  $ pip install pytest-html
  $ pytest --env-config shell-example.yaml --html=report.html

JUnit XML
^^^^^^^^^
JUnit XML reports can be generated directly by pytest and are especially useful for
use in CI systems such as `Jenkins <https://jenkins.io/>`_ with the `JUnit
Plugin <https://wiki.jenkins-ci.org/display/JENKINS/JUnit+Plugin>`_.

They can also be converted to other formats, such as HTML with `junit2html tool
<https://pypi.python.org/pypi/junit2html>`_:

.. code-block:: bash

  $ pip install junit2html
  $ pytest --env-config shell-example.yaml --junit-xml=report.xml
  $ junit2html report.xml

Command-Line
------------

Labgrid contains some command line tools which are used for remote access to
resources.
See :doc:`man/client`, :doc:`man/device-config` and :doc:`man/exporter` for
more information.
