Usage
=====

Installation
------------

The default installation is available via PyPI:

.. code-block:: bash

    $ pip install labgrid

or by cloning the repository and installing manually:

.. code-block:: bash

    $ git clone https://github.com/labgrid-project/labgrid
    $ cd labgrid && python3 setup.py install

Extra requires
~~~~~~~~~~~~~~
Labgrid supports different extras:

- onewire: install onewire support, requires ``onewire>=0.0.2`` from PyPI and
  additionally ``libow-dev`` on debian based distributions.
- coordinator: installs required depencies to start a crossbar coordinator

The extras can be selected by passing them after the package name in square
brackets:

.. code-block:: bash

    $ pip install labgrid[onewire]

or to enable both:

.. code-block:: bash

    $ pip install labgrid[onewire,coordinator]

Depending on the used shell settings, they may have to be escaped via ``\``.

Standalone
------------------

The Labgrid library consists of a set of fixtures which implement the automatic
creation of targets, drivers and synchronisation helpers. The configuration file
`environment.yaml` specifies how the library assembles these fixtures into
working targets. Certain functionality depends upon the availability of a
specific resource or driver, the parser will throw an error and a helpful
message if this is the case.

Scripting usage
~~~~~~~~~~~~~~~

Although the environment creates all the instances by itself, the test editor
still has to create the appropriate fixtures for each device. The environment,
the targets can be extracted by using the function `get_target`.

Example:
::

   from labgrid import Environment

   env = Environment()
   t1 = environment.get_target('target1')
   t2 = environment.get_target('target2')

Pytest Plugin
-------------
Labgrid provides a pytest-plugin as an entry point. It needs the --env-config=
configuration option to be set and creates environment and targets by itself.
