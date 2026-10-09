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
--tls
    enable TLS gRPC channel
--cert
    path to server TLS certificate (in PEM format)
--key
    path to TLS key (in PEM format)
--auth-plugin
    name of the Coordinator authentication plugin
-d, --debug
    enable debug mode

HEALTH CHECKING
---------------

The ``grpc.health.v1.Health`` service reports the same status for both the
``""`` and ``labgrid.Coordinator`` services.
``SERVING`` means the Coordinator is ready to service RPCs.
``NOT_SERVING`` means the Coordinator is in the process of startup or graceful shutdown.

Check a plaintext listener with `grpcurl <https://github.com/fullstorydev/grpcurl>`_:

.. code-block:: console

   $ grpcurl -plaintext -d '{"service":""}' 127.0.0.1:20408 grpc.health.v1.Health/Check

Watch status changes on a plaintext listener:

.. code-block:: console

   $ grpcurl -plaintext -d '{"service":""}' 127.0.0.1:20408 grpc.health.v1.Health/Watch

For TLS, replace ``-plaintext`` with the appropriate TLS options.
``Check`` returns the current status; ``Watch`` streams the initial status and
changes. Unknown names return gRPC ``NOT_FOUND`` from ``Check`` or
``SERVICE_UNKNOWN`` from ``Watch``, which stays open.

TLS WITH A REVERSE PROXY
------------------------

Instead of enabling TLS in ``labgrid-coordinator`` directly, a reverse proxy can
terminate TLS and forward cleartext gRPC to the coordinator. For example, with
``nginx``:

.. code-block:: nginx

   server {
       listen 20407 ssl http2;
       server_name labgrid.example.com;

       ssl_certificate     /etc/ssl/labgrid-coordinator.crt;
       ssl_certificate_key /etc/ssl/labgrid-coordinator.key;

       location / {
           grpc_pass grpc://127.0.0.1:20408;
       }
   }

In this setup, start ``labgrid-coordinator`` without ``--tls`` and point
``labgrid-client`` and ``labgrid-exporter`` at the reverse proxy using
``--tls``.


SEE ALSO
--------

``labgrid-client``\(1), ``labgrid-exporter``\(1)
