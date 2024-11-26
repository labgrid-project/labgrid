=====================
 labgrid-coordinator
=====================

labgrid-coordinator managing labgrid resources and places
=========================================================


:Author: Rouven Czerwinski <r.czerwinski@pengutronix.de>
:organization: Labgrid-Project
:Date:   2024-08-06
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
-A, --auth
    enables gRPC connection authentication/authorization
-cp RELATIVE_PATH, --cert-path RELATIVE_PATH
    relative path to the SSL certificate file, defaults to ``certificates/server.crt``
-kp RELATIVE_PATH, --key-path RELATIVE_PATH
    relative path to the SSL key file, defaults to ``certificates/server.key``
-si AUTH_PLUGIN_NAME, --server-interceptor AUTH_PLUGIN_NAME
    name of the entry point used to return an instance of the custom authentication plugin;
    by default, the 'DefaultAuthMetadataPlugin' is used

-A / --auth
~~~~~~~~~~~~
This option enables gRPC connection authentication/authorization.

-cp / --cert-path
~~~~~~~~~~~~~~~~~
The relative path to the SSL certificate file used for the gRPC channel encryption,
defaults to ``certificates/server.crt``.
The value related to this option is considered only when the gRPC connection authentication is enabled.

-kp / --key-path
~~~~~~~~~~~~~~~~~
The relative path to the SSL key file used for the gRPC channel encryption,
defaults to ``certificates/server.key``.
The value related to this option is considered only when the gRPC connection authentication is enabled.

-si / --server-interceptor
~~~~~~~~~~~~~~~~~~~~~~~~~~
The name of the entry point used to return an instance of the custom server interceptor plugin.
This plugin is delivered as an independent Python package (not part of the labgrid code base).
The server interceptor plugin is a class derived from the ``grpc.aio.ServerInterceptor`` class.
By default, the ``DefaultServerInterceptor`` is used, this default plugin is a part of the labgrid.
This parameter is only considered when the gRPC authentication is enabled.


SEE ALSO
--------

``labgrid-client``\(1), ``labgrid-exporter``\(1)
