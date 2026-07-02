=====================
 labgrid-coordinator
=====================

labgrid-coordinator managing labgrid resources and places
=========================================================

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
-e FILE, --environment FILE
    serve the given YAML env file to clients via the ``GetEnvironment`` RPC.
    Clients opt in by setting ``LG_ENV=coordinator:`` (see
    ``labgrid-client``\(1))
-d, --debug
    enable debug mode

-e / --environment
~~~~~~~~~~~~~~~~~~
When this option is set the coordinator reads the file fresh on each
``GetEnvironment`` request and returns its contents verbatim to the client.
This means a remote user no longer needs a local copy of the env file - they
only need network access to the coordinator.

The default (no ``--environment``) is unchanged: ``GetEnvironment`` returns an
empty string and clients keep loading env from a local file as before.

SEE ALSO
--------

``labgrid-client``\(1), ``labgrid-exporter``\(1)
