Welcome to labgrid's documentation!
===================================

labgrid is an embedded board control python library with a focus on testing, development
and general automation.
It includes a remote control layer to control boards connected to other hosts.

The idea behind labgrid is to create an abstraction of the hardware control
layer needed for testing of embedded systems, automatic software installation
and automation during development.
labgrid itself is *not* a testing framework, but is intended to be combined with
`pytest <https://docs.pytest.org>`_ (and additional pytest plugins).
Please see :doc:`design_decisions` for more background information.

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
- functions to control external services such as emulated USB-Sticks and the
  `hawkBit <https://github.com/eclipse/hawkbit>`_ deployment service

While labgrid is currently used for daily development on embedded boards and for
automated testing, several planned features are not yet implemented and the APIs
may be changed as more use-cases appear.
We appreciate code contributions and feedback on using labgrid on other
environments (see :ref:`contributing` for details).
Please consider contacting us (via a GitHub issue) before starting larger
changes, so we can discuss design trade-offs early and avoid redundant work.
You can also look at :ref:`ideas` for enhancements which are not yet implemented.

.. toctree::
   getting_started
   overview
   usage
   man
   configuration
   development
   design_decisions
   changes
   modules/modules
   :maxdepth: 2
   :caption: Contents


Indices and Tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. meta::
   :google-site-verification: wLmZ0Ehh9wAjp6f23ckkSFyQtNEIW2wUfpv-r5kYv2M
