================
 labgrid-client
================

labgrid-client interface to control boards
==========================================

:Author: Rouven Czerwinski <r.czerwinski@pengutronix.de>
:organization: Labgrid-Project
:Copyright: Copyright (C) 2016-2025 Pengutronix. This library is free software;
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
-x ADDRESS, --coordinator ADDRESS
    coordinator ``HOST[:PORT]`` to connect to, defaults to ``127.0.0.1:20408``
-c CONFIG, --config CONFIG
    set the configuration file
-s STATE, --state STATE
    set an initial state before executing a command, requires a configuration
    file and strategy
-i INITIAL_STATE, --initial-state INITIAL_STATE
    strategy state to force into before switching to desired state, requires a
    desired state (``-s``/``--state``/``LG_STATE``)
-d, --debug
    enable debugging
-v, --verbose
    increase verbosity
-P PROXY, --proxy PROXY
    proxy connections over ssh

CONFIGURATION FILE
------------------
The configuration file follows the description in ``labgrid-device-config``\(5).

ENVIRONMENT VARIABLES
---------------------
Various labgrid-client commands use the following environment variable:

LG_PLACE
~~~~~~~~
This variable can be used to specify a place without using the ``-p`` option, the ``-p`` option overrides it.

LG_TOKEN
~~~~~~~~
This variable can be used to specify a reservation for the ``wait`` command and
for the ``+`` place expansion.

LG_STATE
~~~~~~~~
This variable can be used to specify a state which the device transitions into
before executing a command. Requires a configuration file and a Strategy
specified for the device.

LG_INITIAL_STATE
~~~~~~~~~~~~~~~~
This variable can be used to specify an initial state the device is known to
be in.
This is useful during development. The Strategy used must implement the
``force()`` method.
A desired state must be set using ``LG_STATE`` or ``-s``/``--state``.

LG_ENV
~~~~~~
This variable can be used to specify the configuration file to use without
using the ``--config`` option, the ``--config`` option overrides it.

LG_COORDINATOR
~~~~~~~~~~~~~~
This variable can be used to set the default coordinator in the format
``HOST[:PORT]`` (instead of using the ``-x`` option).

LG_PROXY
~~~~~~~~
This variable can be used to specify a SSH proxy hostname which should be used
to connect to the coordinator and any resources which are normally accessed
directly.

LG_HOSTNAME
~~~~~~~~~~~
Override the hostname used when accessing a resource. Typically only useful for
CI pipelines where the hostname may not be consistent between pipeline stages.

LG_USERNAME
~~~~~~~~~~~
Override the username used when accessing a resource. Typically only useful for
CI pipelines where the username may not be consistent between pipeline stages.

LG_SSH_CONNECT_TIMEOUT
~~~~~~~~~~~~~~~~~~~~~~
Set the connection timeout when using SSH (The ``ConnectTimeout`` option). If
unspecified, defaults to 30 seconds.

MATCHES
-------
Match patterns are used to assign a resource to a specific place. The format is:
exporter/group/cls/name, exporter is the name of the exporting machine, group is
a name defined within the exporter, cls is the class of the exported resource
and name is its name. Wild cards in match patterns are explicitly allowed, *
matches anything.

LABGRID-CLIENT COMMANDS
-----------------------
``monitor``                     Monitor events from the coordinator

``resources (r)``               List available resources

``places (p)``                  List available places

``who``                         List acquired places by user

``show``                        Show a place and related resources

``create``                      Add a new place (name supplied by -p parameter)

``delete``                      Delete an existing place

``add-alias`` alias             Add an alias to a place

``del-alias`` alias             Delete an alias from a place

``set-comment`` comment         Update or set the place comment

``set-tags`` key=value          Set place tags (key=value)

``add-match`` match             Add one (or multiple) match pattern(s) to a place, see MATCHES

``del-match`` match             Delete one (or multiple) match pattern(s) from a place, see MATCHES

``add-named-match`` match name  Add one match pattern with a name to a place

``acquire (lock)``              Acquire a place

``allow`` user                  Allow another user to access a place

``release (unlock)``            Release a place

``release-from`` host/user      Atomically release a place, but only if acquired by a specific user.

                                Note that this command returns success as long
                                as the specified user no longer owns the place,
                                meaning it may be acquired by another user or
                                not at all.

``env``                         Generate a labgrid environment file for a place

``power (pw)`` action           Change (or get) a place's power status, where action is one of get, on, off, cycle

``io`` action [name]            Interact with GPIO (OneWire, relays, ...) devices, where action is one of high, low, get

``console (con)`` [name]        Connect to the console

``dfu`` arg                     Run dfu commands

``fastboot`` arg                Run fastboot with argument

``flashscript`` script arg      Run arbitrary script with arguments to flash device

``bootstrap`` filename          Start a bootloader

``sd-mux`` action               Switch USB SD Muxer, where action is one of dut (device-under-test), host, off

``usb-mux`` action              Switch USB Muxer, where action is one of off, dut-device, host-dut, host-device, host-dut+host-device

``ssh`` [command]               Connect via SSH. Additional arguments are passed to ssh.

``scp`` source destination      Transfer file via scp (use ':dir/file' for the remote side)

``rsync`` source destination    Transfer files via rsync (use ':dir/file' for the remote side)

``sshfs`` remotepath mountpoint Mount a remote path via sshfs

``forward``                     Forward local port to remote target

``telnet``                      Connect via telnet

``video``                       Start a video stream

``audio``                       Start an audio stream

``tmc`` command                 Control a USB TMC device

``write-files`` filename(s)     Copy files onto mass storage device

``write-image`` filename        Write images onto block devices (USBSDMux, USB Sticks, …)

``reserve`` filter              Create a reservation

``cancel-reservation`` token    Cancel a pending reservation

``wait`` token                  Wait for a reservation to be allocated

``reservations``                List current reservations

``export`` filename             Export driver information to file (needs environment with drivers)

``version``                     Print the labgrid version

ADDING NAMED RESOURCES
----------------------
If a target contains multiple Resources of the same type, named matches need to
be used to address the individual resources. In addition to the `match` taken by
`add-match`, `add-named-match` also takes a name for the resource. The other
client commands support the name as an optional parameter and will inform the
user that a name is required if multiple resources are found, but no name is
given.

If one of the resources should be used by default when no resource name is
explicitly specified, it can be named ``default``.

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
