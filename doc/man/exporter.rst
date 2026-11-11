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
-c, --coordinator
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
--pystuck
    enable `pystuck <https://github.com/alonho/pystuck>`_ for debugging
--pystuck-port PORT
    use a different pystuck port than 6667

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

CONFIGURATION
-------------
The exporter uses a YAML configuration file which defines groups of related
resources.
See <https://labgrid.readthedocs.io/en/latest/configuration.html#exporter-configuration>
for more information.

ENVIRONMENT VARIABLES
---------------------
The following environment variables can be used to configure
labgrid-exporter.

LG_COORDINATOR
~~~~~~~~~~~~~~
This variable can be used to set the default coordinator in the format
``HOST[:PORT]`` (instead of using the ``-x`` option).

LG_SERIAL_TRACE_DIR
~~~~~~~~~~~~~~~~~~~
When set, the exporter records all serial-port traffic for each
acquired resource into
``<LG_SERIAL_TRACE_DIR>/<board>-<resource>-<user>.log``, where
``<board>`` is the resource group name, ``<resource>`` is the
resource name and ``<user>`` is the acquiring user identity
reported by the coordinator (in ``host/user`` form).  Any character
other than a letter, digit, ``.``, ``_`` or ``-`` is rewritten to
``_``.  Both directions are captured verbatim, and ser2net writes
timestamped OPEN/CLOSE markers at the start and end of each client
connection so the lab admin has an independent record that is not
affected by per-client logging options.

The directory is created on demand; if that fails, a warning is
logged and the port is exported without tracing.  A fresh ser2net
instance is started for each acquire, so repeated acquires by the
same user on the same board append to the same file.  This needs
ser2net 4.2.0 or later.

LG_SERIAL_TRACE_HEXDUMP
~~~~~~~~~~~~~~~~~~~~~~~
When set to ``1`` (and ``LG_SERIAL_TRACE_DIR`` is also set), the
exporter additionally enables ser2net's hexdump format for the
trace.  This prepends a timestamp to every line at the cost of
producing hex+ASCII output instead of readable text.  The
timestamps have a resolution of one second.  Use this when knowing
when each command was typed matters more than readability.

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
