Labgrid Docker files
====================

Purpose
-------
This folder docker files to build one shared Docker image for the following Labgrid instances/containers.
In staging the a docker-compose file describe how to use the image to start up the following instances:

- **labgrid coordinator** (Crossbar) This instance simply configures a Labgrid coordinator instance.
- **labgrid client** This instance contains the Labgrid client tools.
- **labgrid exporter** This instance contains the Labgrid exporter tools.


Desired architecture
--------------------
The docker image in this repository is thought to be used in a distributed setting, where a coordinator, client and exporter are utilized, as described in the `docs <https://labgrid.readthedocs.io/en/latest/getting_started.html#setting-up-the-distributed-infrastructure>`_

Build
-----
The docker image must be build from the repository root as it copy in the labgrid code, hence in order to buiĺd from "./labgrid/":

  .. code-block:: bash

     $ docker build -f docker/Dockerfile .

Staging - Test environment
--------------------------
In *staging* a docker compose based staging environment resides. The staging environment contains a coordinator, an exporter and a client instance. Moreover a simple example configuration is provided to expose the USB serial on the Host. **Note** It is assumed that /dev/ttyUSB0 is available on the host to run the staging. It is also assumed that the serial is connected to the DUT.

Each container can be started individually with the appropriate debug TTY attached:

Coordinator
...........

  .. code-block:: bash

     $ docker-compose up coordinator

Exporter
........

  .. code-block:: bash

     $ docker-compose up exporter

Client
......

  .. code-block:: bash

     $ docker-compose up -d client

As the client require an interactive shell, this can be achieved as described below, where an interactive shell is opened and the client is used to list the resources seen be the coordinator:

  .. code-block:: bash

     $ docker-compose exec client /bin/bash
     $ labgrid-client -x ws://coordinator:20408/ws resources

If debug TTY's are not needed the staging environment is simply started by:

  .. code-block:: bash

     $ docker-compose up -d

The client can still be accessed by exec as described above.
