Getting Started
===============

This section of the manual contains introductory tutorials for installing
labgrid, running your first test and setting up the distributed infrastructure.
For an overview about the basic design and components of *labgrid*, read the
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
    usage: labgrid-client [-h] [-x ADDRESS] [-c CONFIG] [-p PLACE] [-d] COMMAND ...
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
Onewire support requires the ``libow`` library with headers, installable on debian
via the ``libow-dev`` package. Use the ``onewire`` extra to install the correct
onewire library version in addition to the normal installation.

SNMP
++++
SNMP support requires to additional packages, ``pysnmp`` and ``pysnmpmibs``. They
are included in the ``snmp`` extra.

Modbus
++++++
Modbus support requires an additional package ``pyModbusTCP``. It is included in
the ``modbus`` extra.

ModbusRTU
+++++++++
Modbus support requires an additional package ``minimalmodbus``. It is included in
the ``modbusrtu`` extra.

OpenTelemetry
+++++++++++++
Tracing and metrics can be emitted from the Labgrid Coordinator and Exporter when the OpenTelemetry SDK is installed.
It is included in the ``otel`` extra.

Running Your First Test
-----------------------

Start by copying the initial example:

.. code-block:: bash

    $ mkdir ../first_test/
    $ cp examples/shell/* ../first_test/
    $ cd ../first_test/

Connect your embedded board (raspberry pi, riotboard, …) to your computer and
adjust the ``port`` parameter of the ``RawSerialPort`` resource and ``username``
and ``password`` of the ShellDriver driver in the environment file ``local.yaml``:

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
            prompt: 'root@[\w-]+:[^ ]+ '
            login_prompt: ' login: '
            username: 'root'

For, now it is sufficient to know that labgrid tries to "bind" appropriate drivers
and resources to each other automatically if possible. The ``ShellDriver`` will use
the ``SerialDriver`` to connect to the ``RawSerialPort`` resource. If an automatic
binding is not possible due to ambiguity, the bindings can also be specified
explicitly.

More information about this and the environment configuration file in general can
be found :ref:`here <environment-configuration>`.

You can check which device name gets assigned to your USB-Serial converter by
unplugging the converter, running ``dmesg -w`` and plugging it back in. Boot up
your board (manually) and run your first test:

.. code-block:: bash

    labgrid-venv $ pytest --lg-env local.yaml --capture=no test_shell.py

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

We can simply start the coordinator:

.. code-block:: bash

    labgrid-venv $ labgrid-coordinator

Exporter
~~~~~~~~

The exporter is responsible for exporting resources to the client. It is noted
that drivers are not handled by the exporter. In the distributed case, drivers
are managed by the client.

The exporter needs a configuration file written in YAML syntax, listing
the resources to be exported from the local machine.
The config file contains one or more named resource groups.
Each group contains one or more resource declarations and optionally a location
string.

For example, to export a ``USBSerialPort`` with ``ID_SERIAL_SHORT`` of
``ID23421JLK``, the group name ``example-group`` and the location
``example-location``:

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

More information about the exporter configuration file can be found
:ref:`here <exporter-configuration>`.

Restart the exporter to activate the new configuration.

.. Attention::
   The :any:`ManagedFile` will create temporary uploads in the exporters
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
``example-group`` and ``example-group-2`` should be available there.

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

You can now add a place to the coordinator with:

.. code-block:: bash

    labgrid-venv $ labgrid-client --place example-place create

And add resources to this place (``-p`` is short for ``--place``):

.. code-block:: bash

    labgrid-venv $ labgrid-client -p example-place add-match */example-group/*

Which adds the previously defined resource from the exporter to the place.
To interact with this place, it needs to be acquired first, this is done by

.. code-block:: bash

    labgrid-venv $ labgrid-client -p example-place acquire

For short-lived access, a place can also be leased using a reservation:

.. code-block:: bash

    labgrid-venv $ eval "$(labgrid-client reserve --shell board=example)"
    labgrid-venv $ labgrid-client wait
    labgrid-venv $ labgrid-client -p + lease

Now we can connect to the serial console:

.. code-block:: bash

    labgrid-venv $ labgrid-client -p example-place console

.. note:: Using remote connection requires ``microcom`` or ``telnet`` installed
   on the host where the labgrid-client is called.

See :ref:`remote-usage` for some more advanced features.
For a complete reference have a look at the :doc:`labgrid-client(1) <man/client>`
man page.

Now, to connect drivers to the resources, you can configure an environment file,
which we call ``remote.yaml`` in this case:

.. code-block:: yaml

    targets:
      main:
        resources:
          RemotePlace:
            name: myplace
        drivers:
          SerialDriver: {}
          ShellDriver:
            prompt: 'root@[\w-]+:[^ ]+ '
            login_prompt: ' login: '
            username: 'root'

The ``RemotePlace`` resource makes all resources available that are assigned to
to the place ``myplace`` on your coordinator.

Now, this environment file can be used interactively with the client:

.. code-block:: bash

    labgrid-venv $ labgrid-client -c remote.yaml acquire
    labgrid-venv $ labgrid-client -c remote.yaml console
    labgrid-venv $ labgrid-client -c remote.yaml release

or directly with a test:

.. code-block:: bash

    labgrid-venv $ labgrid-client -c remote.yaml acquire
    labgrid-venv $ pytest --lg-env remote.yaml test_shell.py
    labgrid-venv $ labgrid-client -c remote.yaml release

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
#. If you use labgrid helpers (see :file:`helpers/`) with sudo on exporter,
   replace ``DynamicUser`` with ``User`` and ``Group`` in the
   :file:`labgrid-exporter.service`:

   .. code-block::

      User=labgrid
      Group=labgrid

#. Adjust the ``SupplementaryGroups`` option in the
   :file:`labgrid-exporter.service` file to your distribution so that the
   exporter gains read and write access on TTY devices (for ``ser2net``); most
   often, these groups are called ``dialout``, ``plugdev`` or ``tty``.
   Depending on your udev configuration, you may need multiple groups.
#. Set the coordinator address the exporter should connect to by overriding the
   exporter service file; i.e. execute ``systemctl edit
   labgrid-exporter.service`` and add the following snippet:

   .. code-block::

      [Service]
      Environment="LG_COORDINATOR=<your-host>[:<your-port>]"

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
   to the ``labgrid`` group on the exporter machine:

   .. code-block:: console

      # usermod -a -G labgrid <user>

Enabling gRPC connection security
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

It is encouraged to use TLS for gRPC channels in a production environment.

This can be enabled on the ``labgrid-coordinator`` by adding the ``--tls``,
``--cert`` and ``--key`` options.
Refer to the ``labgrid-coordinator`` man page for details.

When you are connecting with ``labgrid-client`` or ``labgrid-exporter`` to a
``labgrid-coordinator`` that has TLS gRPC channels enabled you need to pass
the ``--tls`` option. If ``--cacert`` is not set, labgrid uses the host CA
certificates to verify the coordinator certificate. Use ``--cacert`` to provide
a specific CA certificate or CA bundle instead.
Refer to the ``labgrid-client`` and ``labgrid-exporter`` man pages for details.
For ``RemotePlace`` connections from an environment config, set the
``coordinator_tls`` option or set ``LG_COORDINATOR_TLS=true`` (or ``1``). If
``coordinator_cacert`` is not set, labgrid uses the host CA certificates. Set
``coordinator_cacert`` to provide a specific CA certificate or CA bundle
instead.

Collecting OpenTelemetry Traces and Metrics
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When the ``otel`` extra is installed, the Labgrid Coordinator and Exporter send
traces over OTLP using gRPC and expose Prometheus-compatible metrics endpoints
by default. Metrics can also be exported over OTLP. OTLP telemetry is sent to
``http://localhost:4317``.

You can customise the OTLP endpoint for each process by setting the
``OTEL_EXPORTER_OTLP_ENDPOINT`` environment variable.
To send metrics to a different endpoint, set
``OTEL_EXPORTER_OTLP_METRICS_ENDPOINT``. OTLP metrics are exported every 60
seconds by default; set ``OTEL_METRIC_EXPORT_INTERVAL`` to change the interval
in milliseconds.
Environment variable usage is described in:
<https://opentelemetry.io/docs/languages/sdk-configuration/otlp-exporter/>.

Set ``OTEL_TRACES_EXPORTER=none`` to disable tracing while keeping metrics
enabled. Set ``OTEL_METRICS_EXPORTER=none`` to disable metrics while keeping
tracing enabled.
By default, when Labgrid creates its ``MeterProvider``, metrics are exposed only
through Prometheus. Set ``OTEL_METRICS_EXPORTER=otlp`` to export only over OTLP,
or set ``OTEL_METRICS_EXPORTER=prometheus,otlp`` to enable both outputs.
Unsupported values, and combining ``none`` with another value, cause a runtime
error.

To configure the providers used for coordinator or exporter traces and metrics,
start the relevant process with the OpenTelemetry launcher:

.. code-block:: bash

    $ python -m pip install opentelemetry-distro
    $ OTEL_SERVICE_NAME=labgrid-coordinator \
        OTEL_METRICS_EXPORTER=otlp \
        OTEL_EXPORTER_OTLP_ENDPOINT=http://collector:4317 \
        opentelemetry-instrument labgrid-coordinator

For an exporter, replace both occurrences of ``labgrid-coordinator`` with
``labgrid-exporter`` and include its normal arguments.

The launcher creates the ``TracerProvider`` and ``MeterProvider`` before
Labgrid starts. Labgrid reuses those providers instead of adding its default
OTLP span processor or creating its default metric readers and Prometheus
server.

For advanced use, applications that start the coordinator or exporter from
Python can register standard OpenTelemetry SDK providers directly with
``opentelemetry.trace.set_tracer_provider()`` and
``opentelemetry.metrics.set_meter_provider()`` before starting it in the same
Python process. Other provider implementations are not currently supported.

When Labgrid creates its default ``MeterProvider``, each Coordinator and
Exporter process exposes its own metrics server at
``http://localhost:9464/metrics`` by default. The metrics endpoint host and port
can be configured for each process with the
``OTEL_EXPORTER_PROMETHEUS_HOST`` and ``OTEL_EXPORTER_PROMETHEUS_PORT``
environment variables. To access the endpoint from another host or container,
set ``OTEL_EXPORTER_PROMETHEUS_HOST`` to a reachable bind address such as
``0.0.0.0``.

When a Coordinator and Exporter run on the same host, assign them different
ports, for example ``9464`` for the Coordinator and ``9465`` for the Exporter.
Keep the Coordinator on its default and start the Exporter with
``OTEL_EXPORTER_PROMETHEUS_PORT=9465 labgrid-exporter ...``.
Port conflicts fail at startup; there is no automatic fallback.
Configure each endpoint as a separate Prometheus scrape target.

The Coordinator exposes the following metrics:

- ``labgrid_coordinator_places_registered``: places registered with the
  Coordinator.
- ``labgrid_coordinator_places_acquired``: places currently acquired.
- ``labgrid_coordinator_places_available``: places currently available for
  scheduler allocation.
- ``labgrid_coordinator_reservations_waiting``: reservations waiting for a
  matching place.
- ``labgrid_coordinator_reservation_wait_duration_seconds``: histogram of the
  time from reservation creation until first allocation.
- ``labgrid_coordinator_reservations_allocated``: reservations holding one or
  more place allocations.
- ``labgrid_coordinator_exporters_connected``: Exporter sessions connected to
  the Coordinator.
- ``labgrid_coordinator_resources_registered``: resources registered by
  connected Exporters.

The Exporter exposes the following resource gauges, grouped by the
``resource_class`` label:

- ``labgrid_exporter_resources_configured``: all configured resources.
- ``labgrid_exporter_resources_free``: available, unacquired resources which
  are not permanently broken.
- ``labgrid_exporter_resources_unavailable``: unavailable resources which are
  not permanently broken, whether acquired or not.
- ``labgrid_exporter_resources_acquired``: resources acquired by a place which
  are not permanently broken.
- ``labgrid_exporter_resources_broken``: permanently broken resources.

- ``labgrid_exporter_resource_commands_total``: resource command results,
  grouped by the ``operation`` and ``outcome`` labels.

For testing collecting telemetry, use
`Grafana OTEL LGTM <https://github.com/grafana/docker-otel-lgtm/>`.
For production telemetry collection, refer to the
`OpenTelemetry Documentation <https://opentelemetry.io/>` for available tools.

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

An example using the pytest plugin is provided under ``examples/strategy``.
