=======================
 labgrid-device-config
=======================

labgrid test configuration files
================================


:Author: Rouven Czerwinski <r.czerwinski@pengutronix.de>
:organization: Labgrid-Project
:Date:   2017-04-15
:Copyright: Copyright (C) 2016-2017 Pengutronix. This library is free software;
            you can redistribute it and/or modify it under the terms of the GNU
            Lesser General Public License as published by the Free Software
            Foundation; either version 2.1 of the License, or (at your option)
            any later version.
:Version: 0.0.1
:Manual section: 5
:Manual group: embedded testing



SYNOPSIS
--------

``*.yaml``

DESCRIPTION
-----------
To integrate a device into a labgrid test, labgrid needs to have a description
of the device and how to access it.

This manual page is divided into section, each describing one top-level yaml key.


TARGETS
-------
The ``targets:`` top key configures a ``target``, it's ``drivers`` and ``resources``.

The top level key is the name of the target, it needs both a ``resources`` and
``drivers`` subkey. The order of instantiated ``resources`` and ``drivers`` is
important, since they are parsed as an ordered dictionary and may depend on a
previous driver.

For a list of available resources and drivers refer to
https://labgrid.readthedocs.io/en/latest/configuration.html.

OPTIONS
-------
The ``options:`` top key configures various options such as the crossbar_url.

OPTIONS KEYS
~~~~~~~~~~~~

``crossbar_url``
  takes as parameter the URL of the crossbar (coordinator) to connect to.
  Defaults to 'ws://127.0.0.1:20408'.

``crossbar_realm``
  takes as parameter the realm of the crossbar (coordinator) to connect to.
  Defaults to 'realm1'.

.. _labgrid-device-config-images:

IMAGES
------
The ``images:`` top key provides paths to access preconfigured images to flash
onto the board. The image paths can be either relative to the YAML file or
absolute.

IMAGE KEYS
~~~~~~~~~~

The subkeys consist of image names as keys and their paths as values. The
corresponding name can than be used with the appropriate tool found under TOOLS.

IMAGE EXAMPLE
~~~~~~~~~~~~~~
Two configured images, one for the root filesystem, one for the bootloader:

::

   images:
     root: "platform-v7a/images/root.img"
     boot: "platform-v7a/images/barebox.img"

TOOLS
-----
The ``tools:`` top key provides paths to binaries such as fastboot.

TOOLS KEYS
~~~~~~~~~~

``fastboot``
    Path to the fastboot binary

``mxs-usb-loader``
    Path to the mxs-usb-loader binary

``imx-usb-loader``
    Path to the imx-usb-loader binary

TOOLS EXAMPLE
~~~~~~~~~~~~~~
Configure the tool path for ``imx-usb-loader``:

::

   tools:
     imx-usb-loader: "/opt/labgrid-helper/imx-usb-loader"

IMPORTS
-------
The ``imports`` key is a list of files or python modules which
are imported by the environment after loading the configuration.
Paths relative to the configuration file are also supported.
This is useful to load drivers and strategy which are contained in your
testsuite, since the import is done before instantiating the targets.

IMPORTS EXAMPLE
~~~~~~~~~~~~~~~
Import a local `myfunctions.py` file:

::

   imports:
     - myfunctions.py

EXAMPLES
--------
A sample configuration with one `main` target, accessible via SerialPort
`/dev/ttyUSB0`, allowing usage of the ShellDriver:

::

   targets:
     main:
       resources:
         RawSerialPort:
           port: "/dev/ttyUSB0"
       drivers:
         SerialDriver: {}
         ShellDriver:
           prompt: 'root@\w+:[^ ]+ '
           login_prompt: ' login: '
           username: 'root'

A sample configuration with `RemotePlace`, using the tools configuration and
importing the local `mystrategy.py` file. The `MyStrategy` strategy is contained
in the loaded local python file:

::

   targets:
     main:
       resources:
         RemotePlace:
           name: test-place
       drivers:
         SerialDriver: {}
         ShellDriver:
           prompt: 'root@\w+:[^ ]+ '
           login_prompt: ' login: '
           username: 'root'
         MyStrategy: {}
	 IMXUSBLoader: {}
   tools:
     imx-usb-loader: "/opt/lg-tools/imx-usb-loader"
   imports:
     - mystrategy.py

SEE ALSO
--------

``labgrid-client``\(1), ``labgrid-exporter``\(1)
 
