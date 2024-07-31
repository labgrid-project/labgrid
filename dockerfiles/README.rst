Labgrid Docker images
=====================

This folder contains Dockerfile's for building Docker images
for the 3 different components of a Labgrid distributed infrastructure.

- **labgrid-coordinator**
  An image with the Labgrid coordinator.
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

   $ docker build --target labgrid-client -t docker.io/labgrid/client -f dockerfiles/Dockerfile .

Using `BuildKit <https://docs.docker.com/develop/develop-images/build_enhancements/>`_
is recommended to reduce build times.

You can also choose to build all 3 images with the included script. The script
will automatically use `docker buildx
<https://docs.docker.com/engine/reference/commandline/buildx/>`` if available.

.. code-block:: bash

   $ pip install --upgrade setuptools_scm
   $ ./dockerfiles/build.sh

The script supports ``podman`` as well.

.. code-block:: bash
  
   $ export DOCKER=podman
   $ ./dockerfiles/build.sh

It builds for the native platform by default. However, building
for foreign platforms is also supported by passing the platform(s) of choice,
e.g. `linux/arm64` as an additional argument.

.. code-block:: bash

   $ pip install --upgrade setuptools_scm
   $ ./dockerfiles/build.sh --platform linux/arm64


Usage
-----

All 3 images are to be considered base images
with the required software installed.
No policy or configuration is done.


labgrid-coordinator usage
~~~~~~~~~~~~~~~~~~~~~~~~~

The labgrid-coordinator image can be used to run a coordinator instance.

It listens on port 20408,
so you probably want to publish that so you can talk to the coordinator.

State is written to ``/opt/coordinator``.
You might want to bind a volume to that
so you can restart the service without losing state.

.. code-block:: bash

   $ docker run -t -p 20408:20408 -v $HOME/coordinator:/opt/coordinator \
	 docker.io/labgrid/coordinator


labgrid-client usage
~~~~~~~~~~~~~~~~~~~~

The labgrid-client image can be used to
run ``labgrid-client`` and ``pytest`` commands.
For example listing available places registered at coordinator at
192.168.1.42:20408

.. code-block:: bash

   $ docker run -e LG_COORDINATOR=192.168.1.42:20408 docker.io/labgrid/client \
	 labgrid-client places

Or running all pytest/labgrid tests at current directory:

.. code-block:: bash

   $ docker run -e LG_COORDINATOR=192.168.1.42:20408 docker.io/labgrid/client \
	 pytest


labgrid-exporter usage
~~~~~~~~~~~~~~~~~~~~~~

The labgrid-exporter image runs a labgrid-exporter
and optionally an ser2net service.

Configuration is not included, but needs to be bind mounted to
/opt/conf/exporter.yaml and /opt/conf/ser2net.conf (optional).

Start it with something like:

.. code-block:: bash

   $ docker run -e LG_COORDINATOR=192.168.1.42:20408 \
       -v $HOME/exporter-conf:/opt/conf \
	 docker.io/labgrid/exporter

If using ser2net or if "exporting" e.g. a serial device, the devices needed must be added to Docker container
(``docker run --device`` option).
Moreover, if using udev this must be mounted in as well: ``docker run -v run/udev:/run/udev:ro``.

Staging
-------

The ``staging`` folder contains a docker compose based example setup, where the images described above are used to
create a setup with the following instances

- **coordinator**
- **exporter**
- **client**
- **dut**

The environment serves both to allow checking if the environment still function after changes, and can act as an example
how to configure the docker images needed to run a minimal setup.

To use the staging environment to conduct a smoke test, first run docker compose to start all services except the
client:

.. code-block:: bash

   $ cd dockerfiles/staging
   $ CURRENT_UID=$(id -u):$(id -g) docker-compose up -d coordinator exporter dut

To run the smoke test just run the client:

.. code-block:: bash

   $ docker-compose up client
