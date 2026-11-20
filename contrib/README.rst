labgrid-webapp
==============

labgrid-webapp implements a browser interface to access some of labgrid's
information.

Quick Start
-----------

.. code-block:: bash

   $ cd labgrid/
   $ source venv/bin/activate
   venv $ pip install -r contrib/requirements-webapp.txt
   venv $ ./contrib/labgrid-webapp --help
   usage: labgrid-webapp [-h] [--coordinator ADDRESS] [--port PORT] [--proxy PROXY]

   Labgrid webapp

   options:
     -h, --help            show this help message and exit
     --coordinator ADDRESS, -x ADDRESS
                           Coordinator address as HOST[:PORT] (default: 127.0.0.1:20408)
     --port PORT           Port to serve on
     --proxy PROXY, -P PROXY

   venv $ ./contrib/labgrid-webapp
   INFO:     Available routes:
   INFO:       - /labgrid/graph
   INFO:     Started server process [2378028]
   INFO:     Waiting for application startup.
   INFO:     Application startup complete.
   INFO:     Uvicorn running on http://0.0.0.0:8800 (Press CTRL+C to quit)
   ...

Please note that the graph feature relies on a valid `graphviz` system
installation. See http://graphviz.org/download/

By default the application will start on port 8800.

To see the graph, go to http://0.0.0.0:8800/labgrid/graph

See http://0.0.0.0:8800/docs for more information on available endpoints.

usb-hubs.py
===========

usb-hubs.py lists the USB hubs below each USB host controller as a tree, with
the ``ID_PATH`` to use when matching a device on one of their ports, for
example in an exporter configuration. ``PORTS`` shows how many of a hub's ports
are in use.

The first line for each controller shows how many devices it has and how many
more it can take: a hub may stop working because its controller is full,
rather than because the hub is faulty. An xHCI controller has a fixed number of
device slots shared by its USB 2 and USB 3 buses, which can only be read from
debugfs, so run the script as root to see it. Other controllers can have up to
127 devices on their bus.

.. code-block:: bash

   $ sudo ./contrib/usb-hubs.py
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
