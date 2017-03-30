.. labgrid documentation master file, created by
   sphinx-quickstart on Mon Feb 20 10:00:00 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to labgrid's documentation!
===================================

Labgrid is a embedded board control library which also supports remote exports and management of embedded boards.

It currently supports:

- pytest-plugin to write tests for embedded systems connecting over SSH or Serial
- remote client-exporter-coordinator infrastructure to make boards available from different computers on a network
- Power/Reset management via plugins for power switches or onewire PIOs
- Upload of binaries via USB: imxusbloader/mxsusbloader (bootloader) or fastboot (kernel)
- Functions to control external services such as emulated USB-Sticks and the Hawkbit deployment service


.. toctree::
   getting_started
   overview
   usage
   man
   configuration
   development
   design_decisions
   modules/modules
   :maxdepth: 2
   :caption: Contents:


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
