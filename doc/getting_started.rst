Getting Started
===============

This section of the manual contains introductory tutorials for installing
labgrid, running your first test and setting up the distributed infrastructure.
For an overview about the basic design and components of `labgrid`, read the
:ref:`overview` first.

Installation
------------

Depending on your distribution you need some dependencies. On Debian these
usually are:

.. code-block:: bash

   $ sudo apt install python3 python3-virtualenv python3-pip python3-setuptools virtualenv microcom


In many cases, the easiest way is to install labgrid into a virtualenv:

.. code-block:: bash

    $ virtualenv -p python3 labgrid-venv
    $ source labgrid-venv/bin/activate
    labgrid-venv $ pip install --upgrade pip

Install Latest Release
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    labgrid-venv $ pip install labgrid

Install Development State
~~~~~~~~~~~~~~~~~~~~~~~~~

Start by cloning the repository and installing labgrid:

.. code-block:: bash

    labgrid-venv $ git clone https://github.com/labgrid-project/labgrid
    labgrid-venv $ cd labgrid && pip install .

.. note::
   If you are **not** installing via pip and intend to use Serial over IP
   (RFC2217), it is highly recommended to uninstall pyserial after installation
   and replace it with the pyserial version from the labgrid project:

   https://github.com/labgrid-project/pyserial/tags

   This pyserial version has two fixes for an Issue we found with Serial over IP
   multiplexers. Additionally it reduces the Serial over IP traffic considerably
   since the port is not reconfigured when labgrid changes the timeout (which is
   done inside the library a lot).

Test Installation
~~~~~~~~~~~~~~~~~

Test your installation by running:

.. code-block:: bash

    labgrid-venv $ labgrid-client --help
    usage: labgrid-client [-h] [-x URL] [-c CONFIG] [-p PLACE] [-d] COMMAND ...
    ...

If the help for labgrid-client does not show up, open an `Issue
<https://github.com/labgrid-project/labgrid/issues>`_. If everything was
successful so far, proceed to the next section:

Optional Requirements
~~~~~~~~~~~~~~~~~~~~~
labgrid provides optional features which are not included in the default
installation. An example for snmp support is:

.. code-block:: bash

    labgrid-venv $ pip install ".[snmp]"

Onewire
+++++++
Onewire support requires the `libow` library with headers, installable on debian
via the `libow-dev` package. Use the `onewire` extra to install the correct
onewire library version in addition to the normal installation.

SNMP
++++
SNMP support requires to additional packages, `pysnmp` and `pysnmpmibs`. They
are included in the `snmp` extra.

Modbus
++++++
Modbus support requires an additional package `pyModbusTCP`. It is included in
the `modbus` extra.

ModbusRTU
+++++++++
Modbus support requires an additional package `minimalmodbus`. It is included in
the `modbusrtu` extra.

Running Your First Test
-----------------------

Start by copying the initial example:

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

    labgrid-venv $ pytest --lg-env local.yaml test_shell.py

It should return successfully, in case it does not, open an `Issue
<https://github.com/labgrid-project/labgrid/issues>`_.

.. _remote-getting-started:

Setting Up the Distributed Infrastructure
-----------------------------------------

The labgrid :ref:`distributed infrastructure <remote-resources-and-places>`
consists of three components:

#. :ref:`overview-coordinator`
#. :ref:`overview-exporter`
#. :ref:`overview-client`

The system needs at least one coordinator and exporter, these can run on the
same machine. The client is used to access functionality provided by an
exporter. Over the course of this tutorial we will set up a coordinator and
exporter, and learn how to access the exporter via the client.

.. Attention::
   Labgrid requires your user to be able to connect from the client machine via
   ssh to the exporter machine _without_ a password prompt. This means that
   public key authentication should be configured on all involved machines for
   your user beforehand.

.. _remote-getting-started-coordinator:

Coordinator
~~~~~~~~~~~

To start the coordinator, we will download the labgrid repository, create an
extra virtualenv and install the dependencies:

.. code-block:: bash

    $ sudo apt install libsnappy-dev
    $ git clone https://github.com/labgrid-project/labgrid
    $ cd labgrid
    $ virtualenv -p python3 crossbar-venv
    $ crossbar-venv/bin/pip install --upgrade pip
    $ crossbar-venv/bin/pip install -r crossbar-requirements.txt
    $ virtualenv -p python3 labgrid-venv
    $ source labgrid-venv/bin/activate
    labgrid-venv $ pip install --upgrade pip
    labgrid-venv $ pip install .

All necessary dependencies should be installed now.

Copy and customize the crossbar config file ``.crossbar/config-anonymous.yaml``
for your use case:

.. code-block:: bash

    labgrid-venv $ cp .crossbar/config-anonymous.yaml .crossbar/my-config.yaml

.. note:: crossbar is a network messaging framework for building distributed
          applications, which labgrid plugs into.

The path to the Python interpreter in the labgrid-venv needs to be configured
in crossbar's config, either manually or with the labgrid-venv being active
via:

.. code-block:: bash

    labgrid-venv $ sed -i "s#^  executable: .*\$#  executable: ${VIRTUAL_ENV}/bin/python3#" .crossbar/my-config.yaml

.. note:: For long running deployments a different ``workdir`` and port may be
          used.
          The crossbar config should reside in a ``.crossbar`` directory in the
          ``workdir`` in this case.
          For an example systemd service file, see
          :ref:`remote-getting-started-systemd-files`.

Now we can finally start the coordinator inside the repository:

.. code-block:: bash

    $ crossbar-venv/bin/crossbar start --config my-config.yaml

.. note:: If --config is specified as a relative path, the config is expected
          in a .crossbar subdirectory (as is the case in the labgrid
          repository).

Exporter
~~~~~~~~

The exporter needs a configuration file written in YAML syntax, listing
the resources to be exported from the local machine.
The config file contains one or more named resource groups.
Each group contains one or more resource declarations and optionally a location
string (see the :doc:`configuration reference <configuration>` for details).

For example, to export a ``USBSerialPort`` with ``ID_SERIAL_SHORT`` of
``ID23421JLK``, the group name `example-group` and the location
`example-location`:

.. code-block:: yaml

   example-group:
     location: example-location
     USBSerialPort:
       match:
         ID_SERIAL_SHORT: ID23421JLK

.. note:: See the :ref:`udev matching section <udev-matching>` on how to
          match ManagedResources and the
          :ref:`resources sections <overview-resources>` for a description of
          different resource types.

The exporter requires additional dependencies:

.. code-block:: bash

    $ sudo apt install ser2net

It can now be started by running:

.. code-block:: bash

    labgrid-venv $ labgrid-exporter configuration.yaml

Additional groups and resources can be added:

.. code-block:: yaml

   example-group:
     location: example-location
     USBSerialPort:
       match:
         ID_SERIAL_SHORT: P-00-00682
       speed: 115200
     NetworkPowerPort:
       model: netio
       host: netio1
       index: 3
   example-group-2:
     USBSerialPort:
       match:
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

    labgrid-venv $ labgrid-client resources
    kiwi/example-group/NetworkPowerPort
    kiwi/example-group/NetworkSerialPort
    kiwi/example-group-2/NetworkSerialPort

You can see the available resources listed by the coordinator. The groups
`example-group` and `example-group-2` should be available there.

To show more details on the exported resources, use ``-v`` (or ``-vv``):

.. code-block:: bash

    labgrid-venv $ labgrid-client -v resources
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

    labgrid-venv $ labgrid-client --place example-place create

And add resources to this place (``-p`` is short for ``--place``):

.. code-block:: bash

    labgrid-venv $ labgrid-client -p example-place add-match */example-group/*

Which adds the previously defined resource from the exporter to the place.
To interact with this place, it needs to be acquired first, this is done by

.. code-block:: bash

    labgrid-venv $ labgrid-client -p example-place acquire

Now we can connect to the serial console:

.. code-block:: bash

    labgrid-venv $ labgrid-client -p example-place console

.. note:: Using remote connection requires ``microcom`` or ``telnet`` installed
   on the host where the labgrid-client is called.

See :ref:`remote-usage` for some more advanced features.
For a complete reference have a look at the :doc:`labgrid-client(1) <man/client>`
man page.

.. _remote-getting-started-systemd-files:

Systemd files
~~~~~~~~~~~~~

Labgrid comes with several systemd files in :file:`contrib/systemd`:

- service files for coordinator and exporter
- tmpfiles.d file to regularly remove files uploaded to the exporter in
  :file:`/var/cache/labgrid`
- sysusers.d file to create the ``labgrid`` user and group, enabling members of
  the ``labgrid`` group to upload files to the exporter in :file:`/var/cache/labgrid`

Follow these instructions to install the systemd files on your machine(s):

#. Copy the service, tmpfiles.d and sysusers.d files to the respective
   installation paths of your distribution.
#. Adapt the ``ExecStart`` paths of the service files to the respective Python
   virtual environments of the coordinator and exporter.
#. Create the coordinator configuration file referenced in the ``ExecStart``
   option of the :file:`labgrid-coordinator.service` file by using
   :file:`.crossbar/config-anonymous.yaml` as a starting point. You most likely
   want to make sure that the ``workdir`` option matches the path given via the
   ``--cbdir`` option in the service file; see
   :ref:`remote-getting-started-coordinator` for further information.
#. Adjust the ``SupplementaryGroups`` option in the
   :file:`labgrid-exporter.service` file to your distribution so that the
   exporter gains read and write access on TTY devices (for ``ser2net``); most
   often, these groups are called ``dialout``, ``plugdev`` or ``tty``.
   Depending on your udev configuration, you may need multiple groups.
#. Set the coordinator URL the exporter should connect to by overriding the
   exporter service file; i.e. execute ``systemctl edit
   labgrid-exporter.service`` and add the following snippet:

   .. code-block::

      [Service]
      Environment="LG_CROSSBAR=ws://<your-host>:<your-port>/ws"

#. Create the ``labgrid`` user and group:

   .. code-block:: console

      # systemd-sysusers

#. Reload the systemd manager configuration:

   .. code-block:: console

      # systemctl daemon-reload

#. Start the coordinator, if applicable:

   .. code-block:: console

      # systemctl start labgrid-coordinator

#. After creating the exporter configuration file referenced in the
   ``ExecStart`` option of the :file:`labgrid-exporter.service` file, start the
   exporter:

   .. code-block:: console

      # systemctl start labgrid-exporter

#. Optionally, for users being able to upload files to the exporter, add them
   to the `labgrid` group on the exporter machine:

   .. code-block:: console

      # usermod -a -G labgrid <user>

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
See the section about the various :ref:`shipped strategies <conf-strategies>`
for examples on this.

An example using the pytest plugin is provided under `examples/strategy`.
