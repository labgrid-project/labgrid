================
 labgrid-client
================

labgrid-client interface to control boards
==========================================

:Author: Rouven Czerwinski <r.czerwinski@pengutronix.de>
:organization: Labgrid-Project
:Date:   2017-04-15
:Copyright: Copyright (C) 2016-2017 Pengutronix. This library is free software;
	    you can redistribute it and/or modify it under the terms of the GNU
	    Lesser General Public License as published by the Free Software
	    Foundation; either version 2.1 of the License, or (at your option)
	    any later version.
:Version: 0.0.1
:Manual section: 1
:Manual group: embedded testing

SYNOPSIS
--------

``labgrid-client`` ``--help``

``labgrid-client`` -p <place> <command>

``labgrid-client`` ``places|resources``

DESCRIPTION
-----------
Labgrid is a scalable infrastructure and test architecture for embedded (linux) systems.

This is the client to control a boards status and interface with it on remote machines.

OPTIONS
-------
-h, --help
    display command line help
-p PLACE, --place PLACE
    specify the place to operate on
-x, --crossbar-url
    the crossbar url of the coordinator
-c CONFIG, --config CONFIG
    set the configuration file
-s STATE, --state STATE
    set an initial state before executing a command, requires a configuration
    file and strategy
-d, --debug
    enable debugging

CONFIGURATION FILE
------------------
The configuration file follows the description in ``labgrid-device-config``\(1).

ENVIRONMENT VARIABLES
---------------------
Various labgrid-client commands use the following environment variable:

PLACE
~~~~~
This variable can be used to specify a place without using the ``-p`` option, the ``-p`` option overrides it.

STATE
~~~~~
This variable can be used to specify a state which the device transitions into
before executing a command. Requires a configuration file and a Strategy
specified for the device.

LG_CROSSBAR
~~~~~~~~~~~
This variable can be used to set the default crossbar URL (instead of using the
``-x`` option).

LG_CROSSBAR_REALM
~~~~~~~~~~~~~~~~~
This variable can be used to set the default crossbar realm to use instead of
``realm1``.

MATCHES
-------
Match patterns are used to assign a resource to a specific place. The format is:
exporter/group/cls/name, exporter is the name of the exporting machine, group is
a name defined within the exporter, cls is the class of the exported resource
and name is its name. Wild cards in match patterns are explicitly allowed, *
matches anything.

LABGRID-CLIENT COMMANDS
-----------------------
``monitor``             Monitor events from the coordinator

``resources (r)``       List available resources

``places (p)``          List available places

``show``                Show a place and related resources

``create``              Add a new place (name supplied by -p parameter)

``delete``              Delete an existing place

``add-alias``           Add an alias to a place

``del-alias``           Delete an alias from a place

``set-comment``         Update or set the place comment

``add-match`` match     Add a match pattern to a place, see MATCHES

``del-match`` match     Delete a match pattern from a place, see MATCHES

``acquire (lock)``      Acquire a place

``release (unlock)``    Release a place

``env``                 Generate a labgrid environment file for a place

``power (pw)`` action   Change (or get) a place's power status, where action is one of get, on, off, status

``console (con)``       Connect to the console

``fastboot``            Run fastboot

``bootstrap``           Start a bootloader

``io``                  Interact with Onewire devices

EXAMPLES
--------

To retrieve a list of places run:

.. code-block:: bash

   $ labgrid-client places


To access a place, it needs to be acquired first, this can be done by running
the ``acquire command`` and passing the placename as a -p parameter:

.. code-block:: bash

   $ labgrid-client -p <placename> acquire

Open a console to the acquired place:

.. code-block:: bash

   $ labgrid-client -p <placename> console

Add all resources with the group "example-group" to the place example-place:

.. code-block:: bash

   $ labgrid-client -p example-place add-match */example-group/*/*


SEE ALSO
--------

``labgrid-exporter``\(1)
