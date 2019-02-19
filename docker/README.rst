Labgrid Docker images
=====================

This folder contains Dockerfile's for building Docker images
for the 3 different components of a Labgrid distributed infrastructure.

- **labgrid-coordinator**
  An image for with crossbar which can be used to run
  a Labgrid coordinator instance.
- **labgrid-client**
  An image with the Labgrid client tools and pytest integration.
- **labgrid-exporter**
  An image with the Labgrid exporter tools.


Build
-----

To build one of the above images,
you need to run the ``docker build`` command in the root of this repository.
Example showing how to build labgrid-client image:

.. code-block:: bash

   $ docker build -t labgrid-client -f docker/client/Dockerfile .

You can also choose to build all 3 images,
with the included script
(which also must be run from the root of this repository):

.. code-block:: bash

   $ ./docker/build.sh


Usage
-----

All 3 images are to be considered base images
with the required software installed.
No policy or configuration is done.


labgrid-coordinator usage
~~~~~~~~~~~~~~~~~~~~~~~~~

The labgrid-coordinator comes with a preconfigured Crossbar.io server.

It listens to port 20408,
so you probably want to publish that so you can talk to the coordinator.

State is written to ``/opt/crossbar``.
You might want to bind a volume to that
so you can restart the service without loosing state.

.. code-block:: bash

   $ docker run -t -p 20408:20408 -v $HOME/crossbar:/opt/crossbar
	 labgrid-coordinator


labgrid-client usage
~~~~~~~~~~~~~~~~~~~~

The labgrid-client image can be used to
run ``labgrid-client`` and ``pytest`` commands.
For example listing available places registered at coordinator at
ws://192.168.1.42:20408/ws

.. code-block:: bash

   $ docker run -e LG_CROSSBAR=ws://192.168.1.42:20408/ws labgrid-client \
	 labgrid-client places

Or running all pytest/labgrid tests at current directory:

.. code-block:: bash

   $ docker run -e LG_CROSSBAR=ws://192.168.1.42:20408/ws labgrid-client \
	 pytest


labgrid-exporter usage
~~~~~~~~~~~~~~~~~~~~~~

The labgrid-exporter image runs a labgrid-exporter
and optionally an ser2net service.

Configuration is not included,
but needs to be bind mounted to
/opt/conf/exporter.yaml and /opt/conf/ser2net.conf (optional).

Start it with something like:

.. code-block:: bash

   $ docker run -e LG_CROSSBAR=ws://192.168.1.42:20408/ws \
       -v $HOME/exporter-conf:/opt/conf \
	 labgrid-coordinator

If using ser2net,
the devices needed must be added to Docker container
(``docker run --device`` option).
