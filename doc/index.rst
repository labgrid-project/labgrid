.. labgrid documentation master file, created by
   sphinx-quickstart on Mon Feb 20 10:00:00 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Labgrid's Documentation!
===================================

Labgrid is an embedded board control library which also supports remote exports and management of embedded boards.

It currently supports:

- pytest-plugin to write tests for embedded systems connecting over SSH or serial lines
- remote client-exporter-coordinator infrastructure to make boards available from different computers on a network
- power/reset management via plugins for power switches or onewire PIOs
- upload of binaries via USB: imxusbloader/mxsusbloader (bootloader) or fastboot (kernel)
- functions to control external services such as emulated USB-sticks and the Hawkbit deployment service


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
