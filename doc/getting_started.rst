=================
 Getting started
=================

This section of the manual contains introductory tutorials to e.g. run your
first test or setup the distributed infrastructure.

Running your first test
=======================

Start by installing labgrid, either by running:

.. code-block:: bash

    $ pip install labgrid

or by cloning the repository and installing manually:

.. code-block:: bash

    $ git clone https://github.com/labgrid-project/labgrid
    $ cd labgrid && python3 setup.py install


test your installation by running:

.. code-block:: bash

    $ labgrid-client --help
    usage: labgrid-client [-h] [-x URL] [-c CONFIG] [-p PLACE] [-d] COMMAND ...

    ...

if the help for labgrid-client does not show up, open an `Issue
<https://github.com/labgrid-project/labgrid/issues>`_. If everything was
successful so far, start by copying the initial example:

.. code-block:: bash

    $ mkdir ../first_test/
    $ cp examples/shell/* ../first_test/ 
    $ cd ../first_test/

connect your embedded board (raspberry pi, riotboard, …) to your computer and
adjust the ``port`` parameter of the ``RawSerialPort`` resource and ``username``
and ``password`` of the ShellDriver driver in ``local.yaml``. You can check
which port gets assigned to your USB-Serial converter by unplugging the
converter, running ``dmesg -w`` and plugging it back in. Boot up your board
(manually) and run your first test:

.. code-block:: bash

    $ pytest --env-config=local.yaml test_shell.py

It should return successfully, in case it does not, open an `Issue
<https://github.com/labgrid-project/labgrid/issues>`_.

Setting up the distributed infrastructure
=========================================

The labgrid distributed infrastructure consists of three components:

#. Coordinator
#. Exporter
#. Client

The system needs at least one coordinator and exporter, these can run on the
same machine. The client is used to access functionality provided by an
exporter. Over the course of this tutorial we will setup a coordinator and
exporter, and learn how to access the exporter via the client.

Coordinator
-----------
To start the coordinator, we will download labgrid and select the coordinator
extra.

.. code-block:: bash

    $ git clone https://github.com/labgrid-project/labgrid
    $ cd labgrid && pip install -e .[coordinator]


All necessary dependencies should be installed now, we can start the coordinator
by running ``crossbar`` inside of the repository.

.. note::  This is possible because the labgrid repository contains a
           description of the coordinator in the ``.crossbar`` folder.

Exporter
--------
The exporter needs a configuration file written in YAML syntax, it lists the
exported resources of the local machine. An entry starts with a name which has a
resource as a subkey, additionally a location key can be provided. Example to
export a ``RawSerialPort`` with the group name `example-port` and the location
`example-location`:

.. code-block:: yaml

   example-port:
     location: example-location
     RawSerialPort:
       port: /dev/ttyUSB0
   example-port-2:
     location: example-location-2
     RawSerialPort:
       port: /dev/ttyUSB1

The exporter can now be started by running:

.. code-block:: bash

    $ labgrid-exporter configuration.yaml

Client
------
Finally we can test the client functionality, run:

.. code-block:: bash

    $ labgrid-client resources

To check the available resources listed by the coordinator, `example-port` and
`example-port-2` should be available there.

You can now add a place with 

.. code-block:: bash

    $ labgrid-client -p `example-place` create

And add resources to this place, for example:

.. code-block:: bash

    $ labgrid-client -p `example-place` add-match */example-port/*

Which adds the previously defined resource from the exporter to the place.
To interact with this place, it needs to be acquired first, this is done by

.. code-block:: bash

    $ labgrid-client -p `example-place` acquire

Now we can connect to the port via console:

.. code-block:: bash

    $ labgrid-client -p `example-place` console

For a complete reference have a look at the ``labgrid-client(1)`` man page.


Udev Matching
=============

Labgrid allows the exporter or environment to match resources via udev rules.
The udev resources become available to the test/exporter as soon es they are
plugged into the computer, e.g. allowing an exporter to export all USB ports on
a specific hub and making a ``NetworkSerialPort`` available as soon as it is
plugged into one of the ports. The information udev has on a device can be
viewed by executing:

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
in the USB-serial converter. The YAML representation to match this converter:


.. code-block:: yaml

   USBSerialPort:
     match:
       ID_SERIAL_SHORT: P-00-00682

This section can now be added under the resource key in a environment
configuration or under its own entry in an exporter configuration file.
