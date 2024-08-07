USB Power and SD-Mux Example
============================

Files
-----

cycle.py
  Python script which uses labgrid as a library and directly cycles power on
  the USBPowerPort.

local.yaml
  Environment configuration to use USBPowerPort, USBSerialPort and
  USBSDMuxDevice resources which are connected locally.

examplestrategy.py
  Custom strategy which controls the USB-SD-Mux and the USB port power.

test_example.py
  Testsuite (based on pytest) to run a simple command in barebox, shell and
  barebox again.

exports.yaml
  Configuration file for labgrid-exporter to export these resources over the
  network.

remote.yaml
  Environment configuration to use USBPowerPort, USBSerialPort and
  USBSDMuxDevice resources which are connected remotely (to the place 'demo1').

Hardware Setup
--------------

This example uses a USB hub which has power control (as supported by `uhubctl
<https://github.com/mvp/uhubctl>`_), a USB serial converter, a `USB-SD-Mux
<https://www.pengutronix.de/de/2017-10-23-usb-sd-mux-automated-sd-card-juggler.html>
board`_ and a USB powered target.
The target is connected on port 1, the serial converer on port2 and the SD-Mux
on port 3.

Software Setup
--------------

The ``uhubctl`` and ``usbsdmux`` tools need to be installed on the system.

Library Example
---------------

Ensure that the hardware is connected and run ``python cycle.py``.
You should get the following output::

  Target: Target(name='main', env=None)
    Resources: [USBPowerPort(target=Target(name='main', env=None), name=None, state=<BindingState.active: 2>, avail=True, timeout=5.0, match={'SUBSYSTEM': 'usb', 'DEVTYPE': 'usb_interface', 'ID_PATH': 'pci-0000:00:14.0-usb-0:2:1.0', 'DRIVER': 'hub'}, device=Device('/sys/devices/pci0000:00/0000:00:14.0/usb1/1-2/1-2:1.0'), index=1)]
    Drivers: [USBPowerDriver(target=Target(name='main', env=None), name=None, state=<BindingState.active: 2>, delay=2.0)]
  Status: True

  === Switching power OFF ===
  Current status for hub 1-2 [05e3:0608 USB2.0 Hub, USB 2.10, 4 ports]
    Port 1: 0100 power
  Sent power off request
  New status for hub 1-2 [05e3:0608 USB2.0 Hub, USB 2.10, 4 ports]
    Port 1: 0000 off
  Status: False

  === Switching power ON ===
  Current status for hub 1-2 [05e3:0608 USB2.0 Hub, USB 2.10, 4 ports]
    Port 1: 0000 off
  Sent power on request
  New status for hub 1-2 [05e3:0608 USB2.0 Hub, USB 2.10, 4 ports]
    Port 1: 0100 power
  Status: True

Local pytest Example
--------------------

Run ``pytest --lg-env local.yaml -v``.
You should get output similar to the following::

  ========================================== test session starts ===========================================
  platform linux -- Python 3.5.3, pytest-3.4.0, py-1.5.2, pluggy-0.6.0 -- /home/jluebbe/ptx/labgrid/venv/bin/python3
  cachedir: ../.pytest_cache
  rootdir: /home/jluebbe/ptx/labgrid/examples, inifile: pytest.ini
  plugins: pylint-0.7.1, mock-1.6.3, isort-0.1.0, cov-2.5.1, labgrid-0.1.1.dev242+ge3d60c7
  collected 3 items
  test_example.py::test_barebox
  Current status for hub 1-2 [05e3:0608 USB2.0 Hub, USB 2.10, 4 ports]
    Port 1: 0100 power
  Sent power off request
  New status for hub 1-2 [05e3:0608 USB2.0 Hub, USB 2.10, 4 ports]
    Port 1: 0000 off
  Current status for hub 1-2 [05e3:0608 USB2.0 Hub, USB 2.10, 4 ports]
    Port 1: 0000 off
  Sent power on request
  New status for hub 1-2 [05e3:0608 USB2.0 Hub, USB 2.10, 4 ports]
    Port 1: 0100 power
  PASSED                                                               [ 33%]
  test_example.py::test_shell
  PASSED                                                               [ 66%]
  test_example.py::test_barebox_2
  Current status for hub 1-2 [05e3:0608 USB2.0 Hub, USB 2.10, 4 ports]
    Port 1: 0100 power
  Sent power off request
  New status for hub 1-2 [05e3:0608 USB2.0 Hub, USB 2.10, 4 ports]
    Port 1: 0000 off
  Current status for hub 1-2 [05e3:0608 USB2.0 Hub, USB 2.10, 4 ports]
    Port 1: 0000 off
  Sent power on request
  New status for hub 1-2 [05e3:0608 USB2.0 Hub, USB 2.10, 4 ports]
    Port 1: 0100 power
  PASSED                                                               [100%]

  ======================================= 3 passed in 23.90 seconds ========================================

Remote Setup
------------

To access resources remotely, you first need to start the coordinator::
  $ labgrid-coordinator
  [...]
  Coordinator ready

Then, you need to start the exporter::
  $ labgrid-exporter exports.yaml
  [...]

Now, you can use ``labgrid-client`` to show resources and configure a place::
  $ labgrid-client resources
  polaris/hub-p1/NetworkUSBPowerPort
  polaris/hub-p2/NetworkUSBPowerPort
  polaris/hub-p2/NetworkSerialPort
  polaris/hub-p3/NetworkUSBPowerPort
  polaris/hub-p3/NetworkUSBSDMuxDevice
  polaris/hub-p4/NetworkUSBPowerPort
  $ labgrid-client -p demo1 create
  $ labgrid-client -p demo1 add-match polaris/hub-p1/NetworkUSBPowerPort
  $ labgrid-client -p demo1 add-match polaris/hub-p2/NetworkSerialPort
  $ labgrid-client -p demo1 add-match polaris/hub-p3/NetworkUSBSDMuxDevice
  $ labgrid-client places
  demo1
  $ labgrid-client -p demo1 lock
  acquired place demo1
  $ labgrid-client -p demo1 show
  Place 'demo1':
    aliases:
    comment:
    matches:
      polaris/hub-p1/NetworkUSBPowerPort
      polaris/hub-p2/NetworkSerialPort
      polaris/hub-p3/NetworkUSBSDMuxDevice
    acquired: polaris/jluebbe
    acquired resources:
      polaris/hub-p1/NetworkUSBPowerPort/USBPowerPort
      polaris/hub-p2/NetworkSerialPort/USBSerialPort
      polaris/hub-p3/NetworkUSBSDMuxDevice/USBSDMuxDevice
    created: 2018-03-20 10:41:07.561995
    changed: 2018-03-20 15:48:25.928298
  Acquired resource 'USBPowerPort' (polaris/hub-p1/NetworkUSBPowerPort/USBPowerPort):
    {'acquired': None,
     'avail': True,
     'cls': 'NetworkUSBPowerPort',
     'params': {'busnum': 1,
		'devnum': 95,
		'host': 'polaris',
		'index': 1,
		'model_id': 1544,
		'path': '1-2',
		'vendor_id': 1507}}
  Acquired resource 'USBSerialPort' (polaris/hub-p2/NetworkSerialPort/USBSerialPort):
    {'acquired': None,
     'avail': True,
     'cls': 'NetworkSerialPort',
     'params': {'extra': {'path': '/dev/ttyUSB0'},
		'host': 'polaris',
		'port': 52363}}
  Acquired resource 'USBSDMuxDevice' (polaris/hub-p3/NetworkUSBSDMuxDevice/USBSDMuxDevice):
    {'acquired': None,
     'avail': True,
     'cls': 'NetworkUSBSDMuxDevice',
     'params': {'busnum': 1,
		'control_path': '/dev/sg1',
		'devnum': 98,
		'host': 'polaris',
		'model_id': 16449,
		'path': '/dev/sdb',
		'vendor_id': 1060}}
  $ labgrid-client who
  User     Host     Place  Changed
  jluebbe  polaris  demo1  2018-03-20 15:50:18.413377
  $ labgrid-client -p demo1 sd-mux dut
  Success
  $ labgrid-client -p demo1 power cycle
  Current status for hub 1-2 [05e3:0608 USB2.0 Hub, USB 2.10, 4 ports]
    Port 1: 0100 power
  Sent power off request
  New status for hub 1-2 [05e3:0608 USB2.0 Hub, USB 2.10, 4 ports]
    Port 1: 0000 off
  Current status for hub 1-2 [05e3:0608 USB2.0 Hub, USB 2.10, 4 ports]
    Port 1: 0000 off
  Sent power on request
  New status for hub 1-2 [05e3:0608 USB2.0 Hub, USB 2.10, 4 ports]
    Port 1: 0100 power
  $ labgrid-client -p demo1 console
  connecting to  NetworkSerialPort(target=Target(name='demo1', env=None), name='USBSerialPort', state=<BindingState.bound: 1>, avail=True, host='polaris', port=52363, speed=115200, protocol='rfc2217') calling  microcom -s 115200 -t polaris:52363
  connected to 127.0.1.1 (port 52363)
  Escape character: Ctrl-\
  Type the escape character followed by c to get to the menu or q to quit


  barebox 2018.03.0-20180308-1 #1 Thu Mar 8 17:11:54 CET 2018


  Board: RaspberryPi 3 Model B
  bcm2835_mci 3f300000.sdhci: registered as 3f300000.sdhci
  bcm2835-gpio 3f200000.gpio: probed gpiochip-1 with base 0
  pitft@0-2: setting up native-CS0 as GPIO 8
  fbtft_of_value: buswidth = 8
  fbtft_of_value: debug = 4294967295
  fbtft_of_value: rotate = 0
  fbtft_of_value: fps = 25
  mci0: detected SD card version 2.0
  mci0: registered disk0
  state: New state registered 'state'
  state: Using bucket 0@0x00000000
  malloc space: 0x0fefe3c0 -> 0x1fdfc77f (size 255 MiB)
  bcm2835_fb bcm2835_fb0: registered

  Hit any key to stop autoboot:
  barebox@RaspberryPi 3 Model B:/

Remote pytest Example
---------------------

Run ``pytest --lg-env remote.yaml -v``.

You should get output very similar to the local pytest example above.
