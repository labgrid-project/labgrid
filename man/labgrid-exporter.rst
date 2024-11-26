==================
 labgrid-exporter
==================

labgrid-exporter interface to control boards
============================================


:Author: Rouven Czerwinski <r.czerwinski@pengutronix.de>
:organization: Labgrid-Project
:Date:   2017-04-15
:Copyright: Copyright (C) 2016-2024 Pengutronix. This library is free software;
            you can redistribute it and/or modify it under the terms of the GNU
            Lesser General Public License as published by the Free Software
            Foundation; either version 2.1 of the License, or (at your option)
            any later version.
:Version: 0.0.1
:Manual section: 1
:Manual group: embedded testing



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
-A, --auth
    enables gRPC connection authentication/authorization
-cp RELATIVE_PATH, --cert-path RELATIVE_PATH
    relative path to the SSL certificate file, defaults to ``certificates/server.crt``
-ap AUTH_PLUGIN_NAME, --auth-plugin AUTH_PLUGIN_NAME
    name of the entry point used to return an instance of the custom authentication plugin;
    by default, the 'DefaultAuthMetadataPlugin' is used

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

-A / --auth
~~~~~~~~~~~~
This option enables gRPC connection authentication/authorization.

-cp / --cert-path
~~~~~~~~~~~~~~~~~
The relative path to the SSL certificate file used for the gRPC channel encryption,
defaults to ``certificates/server.crt``.
The value related to this option is considered only when the gRPC connection authentication is enabled.

-ap / --auth-plugin
~~~~~~~~~~~~~~~~~~~
The name of the entry point used to return an instance of the custom authentication plugin;
this plugin is delivered as an independent Python package (not part of the labgrid code base);
the authentication plugin is a class derived from the ``grpc.AuthMetadataPlugin`` class;
by default, the ``DefaultAuthMetadataPlugin`` is used, this default plugin is a part of the labgrid;
this parameter is only considered when the gRPC authorization/authentication is enabled


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

Start the exporter with the configuration file `my-config.yaml`:

.. code-block:: bash

   $ labgrid-exporter my-config.yaml

Same as above, but with name ``myname``:

.. code-block:: bash

   $ labgrid-exporter -n myname my-config.yaml

To enable basic gRPC authentication:

.. code-block:: bash

    $ labgrid-exporter -A my-config.yaml

SEE ALSO
--------

``labgrid-client``\(1), ``labgrid-device-config``\(5)
