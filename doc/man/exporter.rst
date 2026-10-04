.. _labgrid-exporter:

==================
 labgrid-exporter
==================

labgrid-exporter interface to control boards
============================================

SYNOPSIS
--------

``labgrid-exporter`` ``--help``

``labgrid-exporter`` ``*.yaml``

DESCRIPTION
-----------
Labgrid is a scalable infrastructure and test architecture for embedded (linux) systems.

This is the man page for the exporter, supporting the export of serial ports,
USB devices and various other controllers.

OPTIONS
-------
-h, --help
    display command line help
-x, --coordinator
    coordinator ``HOST[:PORT]`` to connect to, defaults to ``127.0.0.1:20408``
--tls
    enable TLS gRPC channel
--cacert
    path to CA certificate or CA bundle for verifying the coordinator (in PEM format)
-i, --isolated
    enable isolated mode (always request SSH forwards)
-n, --name
    the public name of the exporter
--hostname
    hostname (or IP) published for accessing resources
--fqdn
    use fully qualified domain name as default for hostname
-d, --debug
    enable debug mode
--port-range START-END
    allocate TCP ports from this inclusive range of at least 1000 ports

-i / --isolated
~~~~~~~~~~~~~~~
This option enables isolated mode, which causes all exported resources being
marked as requiring SSH connection forwarding.
Isolated mode is useful when resources (such as NetworkSerialPorts) are not
directly accessible from the clients.
The client will then use SSH to create a port forward to the resource when
needed.

-n / --name
~~~~~~~~~~~
This option is used to configure the exporter name under which resources are
registered with the coordinator, which is useful when running multiple
exporters on the same host.
It defaults to the system hostname.

--hostname
~~~~~~~~~~
For resources like USBSerialPort, USBGenericExport or USBSigrokExport, the
exporter needs to provide a host name to set the exported value of the "host"
key.
If the system hostname is not resolvable via DNS, this option can be used to
override this default with another name (or an IP address).

--fqdn
~~~~~~
In some networks the fully qualified domain name may be needed to reach resources
on an exporter. This option changes the default to fqdn when no --hostname is
explicitly set.

--port-range
~~~~~~~~~~~~
Limit automatic TCP port allocation to an inclusive range, for example ``--port-range=4000-5000``.
This applies to all calls to ``get_free_port()`` in the exporter process, including ser2net and ADB servers.
The range must contain at least 1000 ports between 1 and 65535.
Ports are tried in random order, and occupied ports are skipped.
Allocation fails if no port in the range is available.
Without this option, the operating system chooses an available port.

CONFIGURATION
-------------
The exporter uses a YAML configuration file which defines groups of related
resources.
See <https://labgrid.readthedocs.io/en/latest/configuration.html#exporter-configuration>
for more information.

ENVIRONMENT VARIABLES
---------------------
The following environment variable can be used to configure labgrid-exporter.

LG_COORDINATOR
~~~~~~~~~~~~~~
This variable can be used to set the default coordinator in the format
``HOST[:PORT]`` (instead of using the ``-x`` option).

EXAMPLES
--------

Start the exporter with the configuration file ``my-config.yaml``:

.. code-block:: bash

   $ labgrid-exporter my-config.yaml

Same as above, but with name ``myname``:

.. code-block:: bash

   $ labgrid-exporter -n myname my-config.yaml

Same as above, but connecting to a ``labgrid-coordinator`` that uses TLS gRPC channels:

.. code-block:: bash

    $ labgrid-exporter --tls [--cacert PATH] -n myname my-config.yaml

SEE ALSO
--------

``labgrid-client``\(1), ``labgrid-device-config``\(5)
