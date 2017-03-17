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

Install labgrid into the virtualenv in editable mode:

.. code-block:: bash

   pip install -e .

Tests can now run via:

.. code-block:: bash

   python -m pytest --env-config=<config>

Writing a driver
-------------------

To develop a new driver for labgrid, you need to decide which protocol to
implement, or implement your own protocol. Labgrid uses attr for internal
classes, first of all import attr, the protocol and the common driver class into
your new driver file.

::

    import attr

    from labgrid.driver.common import Driver
    from labgrid.protocol import ConsoleProtocol

Next, define your new class and list the protocols as subclasses of the new
driver class.

::

    import attr

    from labgrid.driver.common import Driver
    from labgrid.protocol import ConsoleProtocol

    @attr.s
    class ExampleDriver(Driver, ConsoleProtocol):
	pass

The ConsoleExpectMixin support a special mixin class to add expect functionality to
any class supporting the ConsoleProtocol, it has to be the first item in the
subclass list.

::

    import attr

    from labgrid.driver.common import Driver
    from labgrid.driver.consoleexpectmixin import ConsoleExpectMixin
    from labgrid.protocol import ConsoleProtocol

    @attr.s
    class ExampleDriver(ConsoleExpectMixin, Driver, ConsoleProtocol)
	pass

Additionally the driver needs to be registered with the target_factory and
provide a bindings dictionary to resolve dependencies on other drivers or
resources.

::
   
    import attr

    from labgrid.factory import target_factory
    from labgrid.driver.common import Driver
    from labgrid.driver.consoleexpectmixin import ConsoleExpectMixin
    from labgrid.protocol import ConsoleProtocol

    @target_factory.reg_driver
    @attr.s
    class ExampleDriver(ConsoleExpectMixin, Driver, ConsoleProtocol)
	bindings = { "port": SerialPort }
	pass

The listed resource :code:`SerialPort` will be bound to :code:`self.port` making it usable
in the class. Checks are performed that the target the driver binds to has a
SerialPort, otherwise an error will be raised. The last thing to be added is the
:code:`__attr_post_init__` function, the minimum requirement is a call to
:code:`super().__attr_post_init__()`.

::
   
    import attr

    from labgrid.factory import target_factory
    from labgrid.driver.common import Driver
    from labgrid.driver.consoleexpectmixin import ConsoleExpectMixin
    from labgrid.protocol import ConsoleProtocol

    @target_factory.reg_driver
    @attr.s
    class ExampleDriver(ConsoleExpectMixin, Driver, ConsoleProtocol)
	bindings = { "port": SerialPort }

	def __attr_post_init__(self):
	    super().__attr_post_init__()

All thats left now is to implement the functionality described by the used protocol.

Writing a resource
-------------------

To add a new resource to labgrid we import attr into our new resource file,
additionaly we need the targetfactory and the common Resource class.

::

    import attr

    from labgrid.factory import target_factory
    from labgrid.driver.common import Resource

Next we add our own resource with the :code:`Resource` common class and register
it with the target_factory.

::

    import attr

    from labgrid.factory import target_factory
    from labgrid.driver.common import Resource


    @target_factory.reg_resource
    @attr.s
    class ExampleResource(Resource):
        pass

All that is left now is to add variables via :code:`attr.ib()` member variables.

::

    import attr

    from labgrid.factory import target_factory
    from labgrid.driver.common import Resource


    @target_factory.reg_resource
    @attr.s
    class ExampleResource(Resource):
        examplevar1 = attr.ib()
        examplevar2 = attr.ib()

The :code:`attr.ib()` style of member definition also supports defaults and
validators, see attrs_.

.. _attrs: https://attrs.readthedocs.io/en/stable/
