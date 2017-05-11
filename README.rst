Welcome to labgrid
==================

|license| |build-status| |coverage-status| |docs-status|

Purpose
-------
Labgrid is a embedded board control python library with a focus on testing, development
and general automation.
It includes a remote control layer to control boards connected to other hosts.

The idea behind labgrid is to create an abstraction of the hardware control
layer needed for testing of embedded systems, automatic software installation
and automation during development.
Labgrid itself is *not* a testing framework, but is intended to be combined with
`pytest <https://docs.pytest.org>`_ (and additional pytest plugins).
Please see `Design Decisions
<https://labgrid.readthedocs.io/en/latest/design_decisions.html>`_ for more
background information.

It currently supports:

- pytest plugin to write tests for embedded systems connecting serial console or
  SSH
- remote client-exporter-coordinator infrastructure to make boards available
  from different computers on a network
- power/reset management via drivers for power switches or onewire PIOs
- upload of binaries via USB: imxusbloader/mxsusbloader (bootloader) or fastboot (kernel)
- functions to control external services such as emulated USB-Sticks and the
  `hawkBit <https://github.com/eclipse/hawkbit>`_ deployment service

While labgrid is currently used for daily development on embedded boards and for
automated testing, several planned features are not yet implemented and the APIs
may be changed as more use-cases appear.
We appreciate code contributions and feedback on using labgrid on other
environments (see `Contributing
<https://labgrid.readthedocs.io/en/latest/development.html#contributing>`_ for
details).
Please consider contacting us (via a GitHub issue) before starting larger
changes, so we can discuss design trade-offs early and avoid redundant work.
You can also look at `Ideas
<https://labgrid.readthedocs.io/en/latest/development.html#ideas>`_ for
enhancements which are not yet implemented.

Documentation
-------------
`Read the Docs <http://labgrid.readthedocs.io/en/latest/>`_

Contributing
------------
`Development Docs <http://labgrid.readthedocs.io/en/latest/development.html>`_

Background
----------
Work on labgrid started at `Pengutronix <http://pengutronix.de/>`_ in late 2016
and is currently in active use and development.

Quickstart
----------
Clone the git repository:

.. code-block:: bash

   $ git clone https://github.com/labgrid-project/labgrid

Create and activate a virtualenv for labgrid:

.. code-block:: bash

   $ virtualenv -p python3 venv
   $ source venv/bin/activate

Install labgrid into the virtualenv:

.. code-block:: bash

   $ python setup.py install

Tests can now run via:

.. code-block:: bash

   $ python -m pytest --lg-env <config>


.. |license| image:: https://img.shields.io/badge/license-LGPLv2.1-blue.svg
    :alt: LGPLv2.1
    :target: https://raw.githubusercontent.com/labgrid-project/labgrid/master/LICENSE.txt

.. |build-status| image:: https://img.shields.io/travis/labgrid-project/labgrid/master.svg?style=flat
    :alt: build status
    :target: https://travis-ci.org/labgrid-project/labgrid

.. |coverage-status| image:: https://img.shields.io/coveralls/labgrid-project/labgrid/master.svg
    :alt: coverage status
    :target: https://coveralls.io/r/labgrid-project/labgrid

.. |docs-status| image:: https://readthedocs.org/projects/labgrid/badge/?version=latest
    :alt: documentation status
    :target: https://labgrid.readthedocs.io/en/latest/?badge=latest
