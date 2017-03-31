Design Decisions
================

This document outlines the design decisions influencing the development of
labgrid.

Out of Scope
------------

Out of scope for labgrid are:

- a build system
- no special images for testing

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
