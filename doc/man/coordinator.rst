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

Before using leases, upgrade all clients and exporters using the coordinator
to versions that support leases.

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

ENVIRONMENT
-----------

``LG_COORDINATOR_POLL_INTERVAL``
    Delay in seconds between runs of each coordinator polling task.
    These tasks save pending state changes, synchronize resources and schedule
    reservations, including handling expired leases.
    A shorter interval makes periodic checks for expired leases more frequent,
    at the cost of running these tasks more often.
    Release can take longer if the coordinator is busy or an exporter fails.

``LG_COORDINATOR_DEFAULT_LEASE_DURATION``
    Initial lease duration in seconds.

``LG_COORDINATOR_DEFAULT_EXTEND_DURATION``
    Seconds added by each successful lease extension.

``LG_COORDINATOR_MAX_LEASE_DURATION``
    Maximum duration in seconds from lease start.
    Initial and extension durations must not exceed this value.

These variables are read and validated by the coordinator before the gRPC server
is created.

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
