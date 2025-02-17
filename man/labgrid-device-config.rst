=======================
 labgrid-device-config
=======================

labgrid test configuration files
================================


:Author: Rouven Czerwinski <r.czerwinski@pengutronix.de>
:organization: Labgrid-Project
:Copyright: Copyright (C) 2016-2025 Pengutronix. This library is free software;
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
The ``options:`` top key configures various options such as the coordinator_address.

OPTIONS KEYS
~~~~~~~~~~~~

``coordinator_address``
  takes as parameter the coordinator ``HOST[:PORT]`` to connect to.
  Defaults to ``127.0.0.1:20408``.

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

``dfu-util``
    Path to the dfu-util binary, used by the DFUDriver.
    See: https://dfu-util.sourceforge.net/

``dpcmd``
    Path to the dpcmd binary, used by the DediprogFlashDriver.
    See: https://github.com/DediProgSW/SF100Linux

``fastboot``
    Path to the fastboot binary, used by the AndroidFastbootDriver.
    See: https://developer.android.com/studio/releases/platform-tools

``flashrom``
    Path to the flashrom binary, used by the FlashromDriver.
    See: https://www.flashrom.org/

``imx_usb``
    Path to the imx_usb binary, used by the BDIMXUSBDriver.
    See: https://github.com/boundarydevices/imx_usb_loader

``imx-usb-loader``
    Path to the imx-usb-loader binary, used by the IMXUSBDriver.
    See: https://git.pengutronix.de/cgit/barebox/tree/scripts/imx/imx-usb-loader.c

``jtagconfig``
    Path to the jtagconfig binary, used by the QuartusHPSDriver.
    See: https://www.intel.com/content/www/us/en/docs/programmable/683689/current/jtagconfig.html

``mxs-usb-loader``
    Path to the mxs-usb-loader binary, used by the MXSUSBDriver.
    See: https://git.pengutronix.de/cgit/barebox/tree/scripts/mxs-usb-loader.c?h=v2017.03.0

``openocd``
    Path to the openocd binary, used by the OpenOCDDriver.
    See: https://openocd.org/

``quartus_hps``
    Path to the quartus_hps binary, used by the QuartusHPSDriver.
    See: https://www.intel.com/content/www/us/en/docs/programmable/683039/22-3/hps-flash-programmer.html

``rk-usb-loader``
    Path to the rk-usb-loader binary, used by the RKUSBDriver.
    See: https://git.pengutronix.de/cgit/barebox/tree/scripts/rk-usb-loader.c

``rsync``
    Path to the rsync binary, used by the SSHDriver.
    See: https://github.com/rsyncproject/rsync

``scp``
    Path to the scp binary, used by the SSHDriver.
    See: https://github.com/openssh/openssh-portable

``sd-mux-ctrl``
    Path to the sd-mux-ctrl binary, used by the USBSDWireDriver.
    See: https://git.tizen.org/cgit/tools/testlab/sd-mux/

``sispmctl``
    Path to the sispmctl binary, used by the SiSPMPowerDriver.
    See: https://sispmctl.sourceforge.net/

``ssh``
    Path to the ssh binary, used by the SSHDriver.
    See: https://github.com/openssh/openssh-portable

``sshfs``
    Path to the sshfs binary, used by the SSHDriver.
    See: https://github.com/libfuse/sshfs

``uhubctl``
    Path to the uhubctl binary, used by the USBPowerDriver.
    See: https://github.com/mvp/uhubctl

``usbmuxctl``
    Path to the usbmuxctl tool, used by the LXAUSBMuxDriver.
    https://github.com/linux-automation/usbmuxctl

``usbsdmux``
    Path to the usbsdmux tool, used by the USBSDMuxDriver.
    See: https://github.com/linux-automation/usbsdmux

``uuu-loader``
    Path to the uuu-loader binary, used by the UUUDriver.
    See: https://github.com/nxp-imx/mfgtools

``ykushcmd``
    Path to the ykushcmd binary, used by the YKUSHPowerDriver.
    See: https://github.com/Yepkit/ykush

The QEMUDriver expects a custom key set via its ``qemu_bin`` argument.
See https://www.qemu.org/

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
           prompt: 'root@[\w-]+:[^ ]+ '
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
           prompt: 'root@[\w-]+:[^ ]+ '
           login_prompt: ' login: '
           username: 'root'
	 IMXUSBDriver: {}
         MyStrategy: {}
   tools:
     imx-usb-loader: "/opt/lg-tools/imx-usb-loader"
   imports:
     - mystrategy.py

SEE ALSO
--------

``labgrid-client``\(1), ``labgrid-exporter``\(1)
 
