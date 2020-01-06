Design Decisions
================

This document outlines the design decisions influencing the development of
labgrid.

Out of Scope
------------

Out of scope for labgrid are:

Integrated Build System
~~~~~~~~~~~~~~~~~~~~~~~

In contrast to some other tools, labgrid explicitly has no support for building
target binaries or images.

Our reasons for this are:

- Several full-featured build systems already exist and work well.
- We want to test unmodified images produced by any build system (OE/Yocto,
  PTXdist, Buildroot, Debian, …).

Test Infrastructure
~~~~~~~~~~~~~~~~~~~

labgrid does not include a test framework.

The main reason is that with `pytest <https://docs.pytest.org/>`_ we already
have a test framework which:

- makes it easy to write tests
- reduces boilerplate code with flexible fixtures
- is easy to extend and has many available plugins
- allows using any Python library for creating inputs or processing outputs
- supports test report generation

Furthermore, the hardware control functionality needed for testing is also very
useful during development, provisioning and other areas, so we don't want to
hide that behind another test framework.

In Scope
--------

- usable as a library for hardware provisioning
- device control via:

  - serial console
  - SSH
  - file management
  - power and reset

- emulation of external services:

  - USB stick emulation
  - external update services (Hawkbit)

- bootstrap services:

  - fastboot
  - imxusbloader

Further Goals
-------------

- tests should be equivalent for workstations and servers
- discoverability of available boards
- distributed board access
