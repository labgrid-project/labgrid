==================
 Design Decisions
==================

This document outlines the design decisions influencing the development of
labgrid.

Out of scope
============

Out of scope for labgrid are:

- a build system
- no special images for testing

In scope
========

- usable as alibrary for hardware provisioning
- device control via:

  - Serial console
  - SSH
  - File management
  - power and reset

- emulation of external services:

  - USB Stick emulation
  - external update services (hawkbit)

- bootstrap services:
  - fastboot
  - imxusbloader

Further goals
=============

- tests should be equivalent for workstations and servers
- discoverability of available boards
- distributed board access
