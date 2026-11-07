=================
 labgrid-suggest
=================

labgrid-suggest generator for YAML config files
===============================================

SYNOPSIS
--------

``labgrid-suggest`` ``--help``

``labgrid-suggest`` ``--debug``

``labgrid-suggest`` ``--list-hubs``

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
--list-hubs
    list the USB hubs and how full each host controller is, then exit

EXAMPLES
--------

For a device that has an ``ID_SERIAL_SHORT`` key with a unique ID embedded
in the USB-serial converter, ``labgrid-suggest`` shows two alternatives:

.. code-block::

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

With ``--list-hubs``, ``labgrid-suggest`` shows the hubs below each USB host
controller, with the ``ID_PATH`` to use when matching a device on one of their
ports.
``PORTS`` shows how many of a hub's ports are in use.
The first line for each controller shows how many devices it has and how many
more it can take: a hub may stop working because its controller is full, rather
than because the hub is faulty.
An xHCI controller has a fixed number of device slots shared by its USB 2 and
USB 3 buses, which can only be read from debugfs, so run ``labgrid-suggest`` as
root to see it.
Other controllers can have up to 127 devices on their bus.

.. code-block::

   Controller 0000:00:14.0 (xhci_hcd): 49 of 64 devices, 15 free
     BUS  PORTS  SPEED  ID_PATH                             DEVICE
     007  7/16   480M   pci-0000:00:14.0                    1d6b:0002  xHCI Host Controller
     007  2/4    480M     pci-0000:00:14.0-usb-0:1          2109:2817  USB2.0 Hub
     007  0/4    480M       pci-0000:00:14.0-usb-0:1.3      2109:2817  USB2.0 Hub
     007  2/4    480M       pci-0000:00:14.0-usb-0:1.4      2109:2817  USB2.0 Hub
     007  1/2    480M         pci-0000:00:14.0-usb-0:1.4.3  18d1:501f  SuzyQable
     ...
     008  2/10   5G     pci-0000:00:14.0                    1d6b:0003  xHCI Host Controller
     008  2/4    5G       pci-0000:00:14.0-usb-0:1          2109:0817  USB3.0 Hub
     ...

   Controller 0000:03:00.2 (ehci-pci): 113 of 127 devices, 14 free
     BUS  PORTS  SPEED  ID_PATH                             DEVICE
     001  4/5    480M   pci-0000:03:00.2                    1d6b:0002  EHCI Host Controller
     001  4/4    480M     pci-0000:03:00.2-usb-0:2          05e3:0610  USB2.1 Hub
     ...

SEE ALSO
--------

``labgrid-device-config``\(5)
