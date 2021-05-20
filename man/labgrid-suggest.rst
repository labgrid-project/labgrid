=================
 labgrid-suggest
=================

labgrid-suggest generator for YAML config files
===============================================


:organization: Labgrid-Project
:Date:   2021-05-20
:Copyright: Copyright (C) 2016-2021 Pengutronix. This library is free software;
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
in the USB-serial converter, the resource match configuration is:

.. code-block:: yaml

   USBSerialPort:
     match:
       '@ID_SERIAL_SHORT': 'P-00-00682'


SEE ALSO
--------

``labgrid-device-config``\(5)
