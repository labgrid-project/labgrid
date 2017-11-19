Getting Started
===============

This section of the manual contains introductory tutorials for installing
labgrid, running your first test and setting up the distributed infrastructure.

Running Your First Test
-----------------------

Depending on your distribution you need some dependencies. On Debian stretch
these usually are:

.. code-block:: bash

   $ apt-get install python3 python3-virtualenv python3-pip


In many cases, the easiest way is to install labgrid into a virtualenv:

.. code-block:: bash

    $ virtualenv -p python3 labgrid-venv
    $ source labgrid-venv/bin/activate

Start by installing labgrid, either by running:

.. code-block:: bash

    $ pip3 install labgrid

or by cloning the repository and installing manually:

.. code-block:: bash

    $ git clone https://github.com/labgrid-project/labgrid
    $ cd labgrid && python3 setup.py install

Test your installation by running:

.. code-block:: bash

    $ labgrid-client --help
    usage: labgrid-client [-h] [-x URL] [-c CONFIG] [-p PLACE] [-d] COMMAND ...
    ...

If the help for labgrid-client does not show up, open an `Issue
<https://github.com/labgrid-project/labgrid/issues>`_. If everything was
successful so far, start by copying the initial example:

.. code-block:: bash

    $ mkdir ../first_test/
    $ cp examples/shell/* ../first_test/
    $ cd ../first_test/

Connect your embedded board (raspberry pi, riotboard, …) to your computer and
adjust the ``port`` parameter of the ``RawSerialPort`` resource and ``username``
and ``password`` of the ShellDriver driver in ``local.yaml``:

.. code-block:: yaml

    targets:
      main:
        resources:
          RawSerialPort:
            port: "/dev/ttyUSB0"
        drivers:
          ManualPowerDriver:
            name: "example"
          SerialDriver: {}
          ShellDriver:
            prompt: 'root@\w+:[^ ]+ '
            login_prompt: ' login: '
            username: 'root'


You can check which device name gets assigned to your USB-Serial converter by
unplugging the converter, running ``dmesg -w`` and plugging it back in. Boot up
your board (manually) and run your first test:

.. code-block:: bash

    $ pytest --lg-env local.yaml test_shell.py

It should return successfully, in case it does not, open an `Issue
<https://github.com/labgrid-project/labgrid/issues>`_.

If you want to build documentation you need some more dependencies:

.. code-block:: bash

   $ pip3 install -r doc-requirements.txt

The documentation is inside ``doc/``.  HTML-Documentation is build using:

.. code-block:: bash

   $ cd doc/
   $ make html

The HTML-documentation is written to ``doc/.build/html/``.


Setting Up the Distributed Infrastructure
-----------------------------------------

The labgrid distributed infrastructure consists of three components:

#. Coordinator
#. Exporter
#. Client

The system needs at least one coordinator and exporter, these can run on the
same machine. The client is used to access functionality provided by an
exporter. Over the course of this tutorial we will set up a coordinator and
exporter, and learn how to access the exporter via the client.

Coordinator
~~~~~~~~~~~

To start the coordinator, we will download labgrid and select the
``coordinator`` extra. You can reuse the virtualenv created in the previous
section.

.. code-block:: bash

    $ git clone https://github.com/labgrid-project/labgrid
    $ cd labgrid && pip install labgrid[coordinator]


All necessary dependencies should be installed now, we can start the coordinator
by running ``crossbar start`` inside of the repository.

.. note:: This is possible because the labgrid repository contains the crossbar
          configuration the coordinator in the ``.crossbar`` folder.

Exporter
~~~~~~~~

The exporter needs a configuration file written in YAML syntax, listing
the resources to be exported from the local machine.
The config file contains one or more named resource groups.
Each group contains one or more resource declarations and optionally a location
string (see the configuration reference for details).

For example, to export a ``RawSerialPort`` with the group name `example-port` and
the location `example-location`:

.. code-block:: yaml

   example-group:
     location: example-location
     RawSerialPort:
       port: /dev/ttyUSB0

The exporter can now be started by running:

.. code-block:: bash

    $ labgrid-exporter configuration.yaml

Additional groups and resources can be added:

.. code-block:: yaml

   example-group:
     location: example-location
     RawSerialPort:
       port: /dev/ttyUSB0
     NetworkPowerPort:
       model: netio
       host: netio1
       index: 3
   example-group-2:
     RawSerialPort:
       port: /dev/ttyUSB1

Restart the exporter to activate the new configuration.

Client
~~~~~~

Finally we can test the client functionality, run:

.. code-block:: bash

    $ labgrid-client resources
    kiwi/example-group/NetworkPowerPort
    kiwi/example-group/RawSerialPort
    kiwi/example-group-2/RawSerialPort

You can see the available resources listed by the coordinator. The groups
`example-group` and `example-group-2` should be available there.

To show more details on the exported resources, use ``-v`` (or ``-vv``):

.. code-block:: bash

    $ labgrid-client -v resources
    Exporter 'kiwi':
      Group 'example-group' (kiwi/example-group/*):
        Resource 'NetworkPowerPort' (kiwi/example-group/NetworkPowerPort[/NetworkPowerPort]):
          {'acquired': None,
           'avail': True,
           'cls': 'NetworkPowerPort',
           'params': {'host': 'netio1', 'index': 3, 'model': 'netio'}}
    ...

You can now add a place with:

.. code-block:: bash

    $ labgrid-client --place example-place create

And add resources to this place (``-p`` is short for ``--place``):

.. code-block:: bash

    $ labgrid-client -p example-place add-match */example-port/*

Which adds the previously defined resource from the exporter to the place.
To interact with this place, it needs to be acquired first, this is done by

.. code-block:: bash

    $ labgrid-client -p example-place acquire

Now we can connect to the serial console:

.. code-block:: bash

    $ labgrid-client -p example-place console

For a complete reference have a look at the ``labgrid-client(1)`` man page.

udev Matching
-------------

Labgrid allows the exporter (or the client-side environment) to match resources
via udev rules.
The udev resources become available to the test/exporter as soon es they are
plugged into the computer, e.g. allowing an exporter to export all USB ports on
a specific hub and making a ``NetworkSerialPort`` available as soon as it is
plugged into one of the hub's ports.
The information udev has on a device can be viewed by executing:

.. code-block:: bash
   :emphasize-lines: 9

    $ udevadm info /dev/ttyUSB0
    ...
    E: ID_MODEL_FROM_DATABASE=CP210x UART Bridge / myAVR mySmartUSB light
    E: ID_MODEL_ID=ea60
    E: ID_PATH=pci-0000:00:14.0-usb-0:5:1.0
    E: ID_PATH_TAG=pci-0000_00_14_0-usb-0_5_1_0
    E: ID_REVISION=0100
    E: ID_SERIAL=Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_P-00-00682
    E: ID_SERIAL_SHORT=P-00-00682
    E: ID_TYPE=generic
    ...

In this case the device has an ``ID_SERIAL_SHORT`` key with a unique ID embedded
in the USB-serial converter.
The resource match configuration for this USB serial converter is:

.. code-block:: yaml
   :emphasize-lines: 3

   USBSerialPort:
     match:
       'ID_SERIAL_SHORT': 'P-00-00682'

This section can now be added under the resource key in an environment
configuration or under its own entry in an exporter configuration file.

Using a Strategy
----------------

Strategies allow the labgrid library to automatically bring the board into a
defined state, e.g. boot through the bootloader into the Linux kernel and log in
to a shell. They have a few requirements:

- A driver implementing the ``PowerProtocol``, if no controllable infrastructure
  is available a ``ManualPowerDriver`` can be used.
- A driver implementing the ``LinuxBootProtocol``, usually a specific driver for
  the board's bootloader
- A driver implementing the ``CommandProtocol``, usually a ``ShellDriver`` with
  a ``SerialDriver`` below it.

Labgrid ships with two builtin strategies, ``BareboxStrategy`` and
``UBootStrategy``. These can be used as a reference example for simple
strategies, more complex tests usually require the implementation of your own
strategies.

To use a strategy, add it and its dependencies to your configuration YAML,
retrieve it in your test and call the ``transition(status)`` function.

.. code-block:: python

   >>> strategy = target.get_driver(strategy)
   >>> strategy.transition("barebox")

An example using the pytest plugin is provided under `examples/strategy`.
