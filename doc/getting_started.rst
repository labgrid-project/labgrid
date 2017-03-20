=================
 Getting started
=================

This section of the manual contains introductory tutorials to e.g. run your
first test or setup the distributed infrastructure.

Running your first test
=======================

Start by installing labgrid, either by running:

.. code-block:: bash

    $ pip install labgrid

or by cloning the repository and installing manually:

.. code-block:: bash

    $ git clone https://github.com/labgrid-project/labgrid
    $ cd labgrid && python3 setup.py install


test your installation by running:

.. code-block:: bash

    $ labgrid-client --help
    usage: labgrid-client [-h] [-x URL] [-c CONFIG] [-p PLACE] [-d] COMMAND ...

    ...

if the help for labgrid-client does not show up, open an `Issue
<https://github.com/labgrid-project/labgrid/issues>`_. If everything was
successful so far, start by copying the initial example:

.. code-block:: bash

    $ mkdir ../first_test/
    $ cp examples/shell/* ../first_test/ 
    $ cd ../first_test/

connect your embedded board (raspberry pi, riotboard, …) to your computer and
adjust the ``port`` parameter of the ``RawSerialPort`` resource and ``username``
and ``password`` of the ShellDrivver drier in ``local.yaml``. You can check
which port gets assigned to your USB-Serial converter by unplugging the
converter, running ``dmesg -w`` and plugging it back in. Boot up your board
(manually) and run your first test:

.. code-block:: bash

    $ pytest --env-config=local.yaml test_shell.py

It should return successfully, in case it does not, open an `Issue
<https://github.com/labgrid-project/labgrid/issues>`_.

Setting up the distributed infrastructure
=========================================

The labgrid distributed infrasctructure consists of three components:

#. Coordinator
#. Exporter
#. Client

The system needs at least one coordinator and exporter, these can run on the
same machine. The client is used to access functionality provided by an
exporter. Over the course of this tutorial we will setup a coordinator and
exporter, and learn how to access the exporter via the client.
