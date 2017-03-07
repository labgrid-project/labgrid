Welcome to labgrid
==================

|license| |build-status| |coverage-status| |docs-status|

Purpose
-------
Labgrid is a embedded board control library which also supports remote exports
and management of embedded boards.

It currently supports:

- pytest-plugin to write tests for embedded systems connecting over SSH or Serial
- remote client-exporter-coordinator infrastructure to make boards available
  from different computers on a network
- Power/Reset management via plugins for power switches or onewire PIOs
- Upload of images via imxusbloader/mxusbloader or fastboot
- Functions to control external services such as emulated USB-Sticks and the
  `Hawkbit <https://github.com/eclipse/hawkbit>`_ deployment service

Documentation
-------------
`Read the docs <http://labgrid.readthedocs.io/en/latest/>`_

Contributing
------------
`Development Docs <http://labgrid.readthedocs.io/en/latest/development.html>`_


Quickstart
----------

Clone the git repository:

.. code-block:: bash

   git clone https://github.com/labgrid-project/labgrid

Create and activate a virtualenv for labgrid:

.. code-block:: bash

   virtualenv -p python3 venv
   source venv/bin/activate


Install required dependencies:

.. code-block:: bash

   sudo apt install libow-dev

Install labgrid into the virtualenv:

.. code-block:: bash

   python setup.py install

Tests can now run via:

.. code-block:: bash

   python -m pytest --env-config=<config>


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
