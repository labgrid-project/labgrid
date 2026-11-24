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
    make coordinator listen on host and port (``HOST:PORT``), defaults to
    ``[::]:20408``
--tls
    enable TLS gRPC channel
--cert
    path to server TLS certificate (in PEM format)
--key
    path to TLS key (in PEM format)
-d, --debug
    enable debug mode (deployments with a large number of exported resources
    will suffer from performance overhead)
--pystuck
    enable `pystuck <https://github.com/alonho/pystuck>`_ for debugging
--pystuck-port PORT
    use a different pystuck port than 6666

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


ENVIRONMENT VARIABLES
---------------------
The following environment variables can be used to configure labgrid-coordinator.

LG_GRPC_KEEPALIVE_TIME_MS
~~~~~~~~~~~~~~~~~~~~~~~~~
Set the interval in milliseconds after which a gRPC keepalive ping is sent to
connected clients and exporters. If unspecified, defaults to 10000 ms.

LG_GRPC_KEEPALIVE_TIMEOUT_MS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Set the time in milliseconds to wait for a keepalive ping acknowledgement
before a connection is considered broken. If unspecified, defaults to 10000 ms.

LG_GRPC_PING_TIMEOUT_MS
~~~~~~~~~~~~~~~~~~~~~~~
Set the gRPC HTTP/2 ping timeout in milliseconds. This also limits how long to
wait for a keepalive ping acknowledgement, so it should be increased together
with ``LG_GRPC_KEEPALIVE_TIMEOUT_MS``. If unspecified, defaults to 15000 ms.

SEE ALSO
--------

``labgrid-client``\(1), ``labgrid-exporter``\(1)
