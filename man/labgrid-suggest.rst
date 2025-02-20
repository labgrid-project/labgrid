=================
 labgrid-suggest
=================

labgrid-suggest generator for YAML config files
===============================================


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

``labgrid-suggest`` ``--help``

``labgrid-suggest`` ``--debug``

DESCRIPTION
-----------
Labgrid is a scalable infrastructure and test architecture for embedded (linux) systems.

This is the man page for a helper tool which will output the proper YAML formatted
snippets for udev scanned devices.
The snippets can be added under the resource key in an environment configuration.

OPTIONS
-------
-h, --help
    display command line help
-d, --debug
    enable debug mode

EXAMPLES
--------

For a device that has an ``ID_SERIAL_SHORT`` key with a unique ID embedded
in the USB-serial converter, ``labgrid-suggest`` shows two alternatives:

.. code-block:: yaml

   === added device ===
   USBSerialPort for /devices/pci0000:00/0000:00:01.3/0000:02:00.0/usb1/1-3/1-3.1/1-3.1:1.0/ttyUSB0/tty/ttyUSB0
   === device properties ===
   device node: /dev/ttyUSB0
   udev tags: , systemd
   vendor: Silicon_Labs
   vendor (DB): Advanced Micro Devices, Inc. [AMD]
   model: CP2102_USB_to_UART_Bridge_Controller
   revision: 0100
   === suggested matches ===
   USBSerialPort:
     match:
       ID_PATH: pci-0000:02:00.0-usb-0:3.1:1.0
   ---
   USBSerialPort:
     match:
       ID_SERIAL_SHORT: P-00-03564
   ---

SEE ALSO
--------

``labgrid-device-config``\(5)
