=====================
 labgrid-coordinator
=====================

labgrid-coordinator managing labgrid resources and places
=========================================================


:Author: Rouven Czerwinski <r.czerwinski@pengutronix.de>
:organization: Labgrid-Project
:Copyright: Copyright (C) 2016-2025 Pengutronix. This library is free software;
            you can redistribute it and/or modify it under the terms of the GNU
            Lesser General Public License as published by the Free Software
            Foundation; either version 2.1 of the License, or (at your option)
            any later version.
:Version: 0.0.1
:Manual section: 1
:Manual group: embedded testing



SYNOPSIS
--------

``labgrid-coordinator`` ``--help``

DESCRIPTION
-----------
Labgrid is a scalable infrastructure and test architecture for embedded (linux)
systems.

This is the man page for the coordinator. Clients and exporters connect to the
coordinator to publish resources, manage place configuration and handle mutual
exclusion.

OPTIONS
-------
-h, --help
    display command line help
-l ADDRESS, --listen ADDRESS
    make coordinator listen on host and port
-d, --debug
    enable debug mode

SEE ALSO
--------

``labgrid-client``\(1), ``labgrid-exporter``\(1)
