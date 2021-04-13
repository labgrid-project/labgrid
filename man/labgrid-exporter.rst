==================
 labgrid-exporter
==================

labgrid-exporter interface to control boards
============================================


:Author: Rouven Czerwinski <r.czerwinski@pengutronix.de>
:organization: Labgrid-Project
:Date:   2017-04-15
:Copyright: Copyright (C) 2016-2017 Pengutronix. This library is free software;
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
-x, --crossbar-url
    the crossbar url of the coordinator
-i, --isolated
    enable isolated mode (always request SSH forwards)
-n, --name
    the public name of the exporter
--hostname
    hostname (or IP) published for accessing resources
--ser2net-port
    ser2net port published for accessing resources (defaults to any free port)
-d, --debug
    enable debug mode

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

--ser2net-port
~~~~~~~~~~~~~~
For the SerialPortExport resource the exporter needs to provide a port number
to ser2net for it to expose the serial console on. Use this argument if you
need a fixed port, for example if running the exporter in a container.  If the
ser2net port is not set, it will default to any open port.

CONFIGURATION
-------------
The exporter uses a YAML configuration file which defines groups of related
resources.
See <https://labgrid.readthedocs.io/en/latest/configuration.html#exporter-configuration>
for more information.

ENVIRONMENT VARIABLES
---------------------
The following environment variable can be used to configure labgrid-exporter.

LG_CROSSBAR
~~~~~~~~~~~
This variable can be used to set the default crossbar URL (instead of using the
``-x`` option).

LG_CROSSBAR_REALM
~~~~~~~~~~~~~~~~~
This variable can be used to set the default crossbar realm to use instead of
``realm1``.

EXAMPLES
--------

Start the exporter with the configuration file `my-config.yaml`:

.. code-block:: bash

   $ labgrid-exporter my-config.yaml

Same as above, but with name ``myname``:

.. code-block:: bash

   $ labgrid-exporter -n myname my-config.yaml

SEE ALSO
--------

``labgrid-client``\(1), ``labgrid-device-config``\(1)
