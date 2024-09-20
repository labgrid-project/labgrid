.. image:: https://raw.githubusercontent.com/labgrid-project/labgrid/master/labgrid_logo.png
   :alt: labgrid logo
   :align: center

Welcome to labgrid
==================
|license| |unit-tests| |docker-build| |coverage-status| |docs-status| |chat| |calver|

Labgrid is an embedded board control python library with a focus on testing, development
and general automation.
It includes a remote control layer to control boards connected to other hosts.

* `Getting started <#Getting-started>`_

* `Purpose and Features <#purpose-and-features>`_

* `Documentation <#documentation>`_

* `Contributing <#contributing>`_

* `Background <#background>`_

* `Installation <#installation>`_

  * `Install Latest Release <#install-latest-release>`_

  * `Install Development State <#install-development-state>`_

Getting started
---------------
There is a tutorial series on the Pengutronix Youtube channel you can follow to
get started: `Labgrid Tutorial Playlist
<https://www.youtube.com/playlist?list=PLPy6BX4pJosCEq7CIU06bt2WM7lFAy1CF>`_.

The other starting point is in the `documentation
<https://labgrid.readthedocs.io/en/latest/getting_started.html>`__.

Purpose and Features
--------------------
The idea behind labgrid is to create an abstraction of the hardware control
layer needed for testing of embedded systems, automatic software installation
and automation during development.
Labgrid itself is *not* a testing framework, but is intended to be combined with
`pytest <https://docs.pytest.org>`_ (and additional pytest plugins).
Please see `Design Decisions
<https://labgrid.readthedocs.io/en/latest/design_decisions.html>`_ for more
background information.

It currently supports:

- remote client-exporter-coordinator infrastructure to make boards available
  from different computers on a network
- pytest plugin to write automated tests for embedded systems
- CLI and library usage for development and automation
- interaction with bootloader and Linux shells on top of serial console or SSH
- power/reset management via drivers for power switches
- upload of binaries and device bootstrapping via USB
- control of digital outputs, SD card and USB multiplexers
- integration of audio/video/measurement devices for remote development and
  testing
- Docker/QEMU integration

While labgrid is currently used for daily development on embedded boards and for
automated testing, several planned features are not yet implemented and the APIs
may be changed as more use-cases appear.
We appreciate code contributions and feedback on using labgrid on other
environments (see `Contributing
<https://labgrid.readthedocs.io/en/latest/development.html#contributing>`__ for
details).
Please consider contacting us (via a GitHub issue) before starting larger
changes, so we can discuss design trade-offs early and avoid redundant work.
You can also look at `Ideas
<https://labgrid.readthedocs.io/en/latest/development.html#ideas>`_ for
enhancements which are not yet implemented.

Documentation
-------------
labgrid's documentation is hosted on `Read the Docs <http://labgrid.readthedocs.io/en/latest/>`_.

Contributing
------------
See our `Development Docs <http://labgrid.readthedocs.io/en/latest/development.html>`_.

Visit us in our IRC channel ``#labgrid`` on libera.chat (bridged to the
`Matrix channel #labgrid:matrix.org <https://app.element.io/#/room/#labgrid:matrix.org>`_)

Background
----------
Work on labgrid started at `Pengutronix <http://pengutronix.de/>`_ in late 2016
and is currently in active use and development.

Installation
------------
See the `Installation section
<http://labgrid.readthedocs.io/en/latest/getting_started.html#installation>`_
for more details.

Install Latest Release
^^^^^^^^^^^^^^^^^^^^^^
Install labgrid via PyPi:

.. code-block:: bash

   $ virtualenv -p python3 venv
   $ source venv/bin/activate
   venv $ pip install --upgrade pip
   venv $ pip install labgrid

Install Development State
^^^^^^^^^^^^^^^^^^^^^^^^^
Clone the git repository:

.. code-block:: bash

   $ git clone https://github.com/labgrid-project/labgrid

Create and activate a virtualenv for labgrid:

.. code-block:: bash

   $ virtualenv -p python3 venv
   $ source venv/bin/activate
   venv $ pip install --upgrade pip


Install labgrid into the virtualenv:

.. code-block:: bash

   venv $ pip install .

Tests can now run via:

.. code-block:: bash

   venv $ python -m pytest --lg-env <config>


.. |license| image:: https://img.shields.io/badge/license-LGPLv2.1-blue.svg
    :alt: LGPLv2.1
    :target: https://raw.githubusercontent.com/labgrid-project/labgrid/master/LICENSE

.. |unit-tests| image:: https://github.com/labgrid-project/labgrid/workflows/unit%20tests/badge.svg
    :alt: unit tests status
    :target: https://github.com/labgrid-project/labgrid/actions?query=workflow%3A%22unit+tests%22+branch%3Amaster

.. |docker-build| image:: https://github.com/labgrid-project/labgrid/workflows/docker%20build/badge.svg
    :alt: docker build status
    :target: https://github.com/labgrid-project/labgrid/actions?query=workflow%3A%22docker+build%22+branch%3Amaster

.. |coverage-status| image:: https://codecov.io/gh/labgrid-project/labgrid/branch/master/graph/badge.svg
    :alt: coverage status
    :target: https://codecov.io/gh/labgrid-project/labgrid

.. |docs-status| image:: https://readthedocs.org/projects/labgrid/badge/?version=latest
    :alt: documentation status
    :target: https://labgrid.readthedocs.io/en/latest/?badge=latest

.. |chat| image:: https://matrix.to/img/matrix-badge.svg
    :alt: chat
    :target: https://app.element.io/#/room/#labgrid:matrix.org

.. |calver| image:: https://img.shields.io/badge/calver-YY.MINOR%5B.MICRO%5D-22bfda.svg
    :alt: chat
    :target: https://calver.org/
