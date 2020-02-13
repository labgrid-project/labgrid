Getting Started
===============

This section of the manual contains introductory tutorials for installing
labgrid, running your first test and setting up the distributed infrastructure.
For an overview about the basic design and components of `labgrid`, read the
:ref:`overview` first.

Installation
------------

Depending on your distribution you need some dependencies. On Debian stretch
these usually are:

.. code-block:: bash

   apt-get install python3 python3-virtualenv python3-pip virtualenv


In many cases, the easiest way is to install labgrid into a virtualenv:

.. code-block:: bash

    virtualenv -p python3 labgrid-venv
    source labgrid-venv/bin/activate

Start installing labgrid by cloning the repository and installing the
requirements from the `requirements.txt` file:

.. code-block:: bash

    git clone https://github.com/labgrid-project/labgrid
    cd labgrid && pip install -r requirements.txt
    python3 setup.py install


Test your installation by running:

.. code-block:: bash

    labgrid-client --help
    # usage: labgrid-client [-h] [-x URL] [-c CONFIG] [-p PLACE] [-d] COMMAND ...
    ...

If the help for labgrid-client does not show up, open an `Issue
<https://github.com/labgrid-project/labgrid/issues>`_. If everything was
successful so far, proceed to the next section:


Ways to use labgrid
-------------------

Labgrid can be used in multiple different use cases. 
The following chapter will explore those use cases through easy to reproduce examples.

Labgrid is board agnostic, but for the sake of providing an example Raspberry Pi 3 will be used. 
For the creation of this example `Raspbian Buster Lite <https://downloads.raspberrypi.org/raspbian_lite_latest>`_ was used as the image on the Pi. 
It is assumed you know how to set up a Pi and connect and use a serial connection.

The USB to serial connection is registered as ``/dev/ttyUSB0``.
Username is ``pi`` password ``raspberry``.

Please make sure you don't have a serial terminal connection with the Pi while running the examples. 
This will cause the example to fail.

If you witness any of the examples fail please open an `Issue <https://github.com/labgrid-project/labgrid/issues>`_.

Code examples are copy pastable even for file creation.
That's what the ``cat > local.yaml << EOF`` are for.

Using labgrid as a library
++++++++++++++++++++++++++

Create the yaml file:

.. code-block:: bash

    # Allow access to the serial termial
    sudo chmod 777 /dev/ttyUSB0

    cat > local.yaml << EOF
    targets:
      main:
        resources:
          RawSerialPort:
            port: "/dev/ttyUSB0"
        drivers:
          SerialDriver: {}
          ShellDriver:
            prompt: 'pi@\w+:[^ ]+ '
            login_prompt: ' login: '
            username: 'pi'
            password: 'raspberry'
    EOF

And the python file where labgrid is used as a library:

.. code-block:: bash

    cat > labgrid_as_lib.py << EOF
    from labgrid import Environment
    
    env_rpi = Environment('local.yaml')
    target_rpi = env_rpi.get_target()
    shell = target_rpi.get_driver('CommandProtocol')
    target_rpi.activate(shell)
    cmd_return = shell.run("cat /proc/version")
    print("Command output: " + str(cmd_return[0][0]))
    print("Exit code: " + str(cmd_return[2]))
    EOF
    

Boot up your board manually and execute:
    
.. code-block:: bash

    python labgrid_as_lib.py


Running this will show the output of ``cat /proc/version`` executed on the Pi.
This example shows some labgrid concepts in action. 

We defined an :ref:`Environment <enviornment-configuration>` for the Pi. 
This is the ``yaml`` file describing our target. 
We called our target ``main``.

We've defined some :ref:`Resources <resources>` and  :ref:`Drivers <drivers-and-protocols>` for the Pi. 
The drivers stack on top of each other as long as they meet the correct conditions.
A  resource is always the lowest member of the stack.
You can check the condition for each driver in :ref:`Configuration <configuration>`.

The top layer of the stack for this example is the :ref:`ShellDriver <shell-driver>`.
It attempts to set the terminal in a state where ``cat /proc/version`` can be executed.
i.e. It wouldn't make sense to execute in the ``login`` prompt or while the board is booting.
The ShellDriver needs to be stacked on top of a driver which implements the :ref:`ConsoleProtocol <drivers-and-protocols>`.
Once that condition is met the ShellDriver can :ref:`bind to and activate <binding-and-activation>` the lower level driver.

In this example, the driver implementing the ConsoleProtocol is the :ref:`SerialDriver <serial-driver>`.
Its duty is to set up the serial terminal to a workable state.
It can only be stacked on top of a certain type of :ref:`Resource <enviornment-configuration>`. 
If the condition is fulfilled the driver will proceed with :ref:`binding and activating <binding-and-activation>` the resource.

In this example the :ref:`Resource <enviornment-configuration>` which meets the condition is :ref:`RawSerialPort <raw-serial-port>`.
It represents the access point through which to reach the Pi we want to control.
Unlike a driver it doesn't provide functionality but is just a description.


Using labgrid to run tests
++++++++++++++++++++++++++

labgrid can also be used to help write tests.
This doesn't conceptually differ from the example above.
The only difference is we're using labgrid from the context of the testing framework ``pytest``.


Start by copying the initial example:

.. code-block:: bash

    # This is in the root dir of the labgrid repo
    mkdir ../first_test/
    cp examples/shell/* ../first_test/
    cd ../first_test/

Copy paste the code below to create the content for ``local.yaml`` to:

.. code-block:: bash

    cat > local.yaml << EOF
    targets:
      main:
        resources:
          RawSerialPort:
            port: "/dev/ttyUSB0"
        drivers:
          SerialDriver: {}
          ShellDriver:
            prompt: 'pi@\w+:[^ ]+ '
            login_prompt: ' login: '
            username: 'pi'
            password: 'raspberry'
    EOF

Boot up your board manually and run your first test:

.. code-block:: bash

    pytest --lg-env local.yaml test_shell.py

If everything worked correctly you should see the output showing you a passed test.


.. _remote-getting-started:

Setting Up the Distributed Infrastructure
+++++++++++++++++++++++++++++++++++++++++

The labgrid :ref:`distributed infrastructure <remote-resources-and-places>`
consists of three components:

#. :ref:`overview-coordinator`
#. :ref:`overview-exporter`
#. :ref:`overview-client`

The system needs at least one coordinator and exporter, these can run on the
same machine. The client is used to access functionality provided by an
exporter. Over the course of this tutorial we will set up a coordinator and
exporter, and learn how to access the exporter via the client.

Coordinator
~~~~~~~~~~~

To start the coordinator, we will download the labgrid repository, create an
extra virtualenv and install the dependencies via the requirements file.

.. code-block:: bash

    $ git clone https://github.com/labgrid-project/labgrid
    $ cd labgrid && virtualenv -p python3 crossbar_venv
    $ source crossbar_venv/bin/activate
    $ pip install -r crossbar-requirements.txt
    $ python setup.py install

All necessary dependencies should be installed now, we can start the coordinator
by running ``crossbar start`` inside of the repository.

.. note:: This is possible because the labgrid repository contains the crossbar
          configuration the coordinator in the ``.crossbar`` folder.
          crossbar is a network messaging framework for building distributed
          applications, which labgrid plugs into.

.. note:: For long running deployments, you should copy and customize the
	  ``.crossbar/config.yaml`` file for your use case. This includes
	  setting a different ``workdir`` and may include changing the running
	  port.

Exporter
~~~~~~~~

The exporter needs a configuration file written in YAML syntax, listing
the resources to be exported from the local machine.
The config file contains one or more named resource groups.
Each group contains one or more resource declarations and optionally a location
string (see the :doc:`configuration reference <configuration>` for details).

For example, to export a ``USBSerialPort`` with ``ID_SERIAL_SHORT`` of
``ID23421JLK``, the group name `example-port` and the location
`example-location`:

.. code-block:: yaml

   example-group:
     location: example-location
     USBSerialPort:
       ID_SERIAL_SHORT: ID23421JLK

.. note:: Use ``labgrid-suggest`` to generate the YAML snippets for most
	  exportable resources.

The exporter can now be started by running:

.. code-block:: bash

    $ labgrid-exporter configuration.yaml

Additional groups and resources can be added:

.. code-block:: yaml

   example-group:
     location: example-location
     USBSerialPort:
       ID_SERIAL_SHORT: ID23421JLK
     NetworkPowerPort:
       model: netio
       host: netio1
       index: 3
   example-group-2:
     USBSerialPort:
       ID_SERIAL_SHORT: KSLAH2341J

Restart the exporter to activate the new configuration.

.. Attention::
   The `ManagedFile` will create temporary uploads in the exporters
   ``/var/cache/labgrid`` directory. This directory needs to be created manually
   and should allow write access for users. The ``/contrib`` directory in the
   labgrid-project contains a tmpfiles configuration example to automatically
   create and clean the directory.
   It is also highly recommended to enable ``fs.protected_regular=1`` and
   ``fs.protected_fifos=1`` for kernels>=4.19, to protect the users from opening
   files not owned by them in world writeable sticky directories.
   For more information see `this kernel commit`_.

.. _`this kernel commit`: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=30aba6656f

Client
~~~~~~

Finally we can test the client functionality, run:

.. code-block:: bash

    $ labgrid-client resources
    kiwi/example-group/NetworkPowerPort
    kiwi/example-group/NetworkSerialPort
    kiwi/example-group-2/NetworkSerialPort

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

See :ref:`remote-usage` for some more advanced features.
For a complete reference have a look at the :doc:`labgrid-client(1) <man/client>`
man page.

udev Matching
-------------

labgrid allows the exporter (or the client-side environment) to match resources
via udev rules.
The udev resources become available to the test/exporter as soon es they are
plugged into the computer, e.g. allowing an exporter to export all USB ports on
a specific hub and making a ``NetworkSerialPort`` available as soon as it is
plugged into one of the hub's ports.
labgrid also provides a small utility called ``labgrid-suggest`` which will
output the proper YAML formatted snippets for you.
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

As the USB bus number can change depending on the kernel driver initialization
order, it is better to use the ``@ID_PATH`` instead of ``@sys_name`` for USB
devices.
In the default udev configuration, the path is not available for all USB
devices, but that can be changed by creating a udev rules file:

.. code-block:: none

  SUBSYSTEMS=="usb", IMPORT{builtin}="path_id"


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

labgrid ships with two builtin strategies, ``BareboxStrategy`` and
``UBootStrategy``. These can be used as a reference example for simple
strategies, more complex tests usually require the implementation of your own
strategies.

To use a strategy, add it and its dependencies to your configuration YAML,
retrieve it in your test and call the ``transition(status)`` function.

.. code-block:: python

   >>> strategy = target.get_driver(strategy)
   >>> strategy.transition("barebox")

An example using the pytest plugin is provided under `examples/strategy`.
