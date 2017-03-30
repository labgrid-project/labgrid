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

Tests can now run via:

.. code-block:: bash

   python -m pytest --env-config=<config>

Writing a driver
-------------------

To develop a new driver for labgrid, you need to decide which protocol to
implement, or implement your own protocol.
If you are unsure about a new protocol's API, just use the driver directly from
the client code, as deciding on a good API will be much easier when another
similiar driver is added.

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

    @attr.s
    class ExampleDriver(Driver, ConsoleProtocol):
	pass

The ConsoleExpectMixin is a mixin class to add expect functionality to any
class supporting the :any:`ConsoleProtocol` and has to be the first item in the
subclass list.
Using is mixin class allows sharing common code, which would otherwise need to
be added into multiple drivers.

::

    import attr

    from labgrid.driver.common import Driver
    from labgrid.driver.consoleexpectmixin import ConsoleExpectMixin
    from labgrid.protocol import ConsoleProtocol

    @attr.s
    class ExampleDriver(ConsoleExpectMixin, Driver, ConsoleProtocol)
	pass

Additionally the driver needs to be registered with the target_factory and
provide a bindings dictionary, so that the :any:`Target` can resolve
dependencies on other drivers or resources.

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

The listed resource :code:`SerialPort` will be bound to :code:`self.port`,
making it usable in the class.
Checks are performed that the target the driver binds to has a SerialPort,
otherwise an error will be raised.

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
    @attr.s
    class ExampleDriver(ConsoleExpectMixin, Driver, ConsoleProtocol)
	bindings = { "port": SerialPort }

	def __attr_post_init__(self):
	    super().__attr_post_init__()

All that's left now is to implement the functionality described by the used
protocol, by using the API of the bound drivers and resources.

Writing a resource
-------------------

To add a new resource to labgrid we import attr into our new resource file,
additionally we need the :any:`target_factory` and the common Resource class.

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
    @attr.s
    class ExampleResource(Resource):
        pass

All that is left now is to add attributes via :code:`attr.ib()` member
variables.

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
validators, see the `attrs documentation <https://attrs.readthedocs.io/en/stable/>`_.
