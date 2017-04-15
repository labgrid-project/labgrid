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
usb tools and various other controllers.

OPTIONS
-------
-h, --help
    display command line help
-x, --crossbar-url
    the crossbar url of the coordinator
-n, --name
    the public name of the exporter

CONFIGURATION
-------------
The exporter uses a YAML configuration file which defines groups of releated
resources.
Furthermore the exporter can start helper binaries such as ``ser2net`` to
export local serial ports over the network.

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
