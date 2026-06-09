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
    path to TLS certificate (in PEM format)
--key
    path to TLS key (in PEM format)
-d, --debug
    enable debug mode

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
