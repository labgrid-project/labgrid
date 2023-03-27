Release 24.0 (unreleased)

New Features in 24.0
~~~~~~~~~~~~~~~~~~~~
- When invoking tests with pytest, the ``--log-(cli|file)-(level|format)``
  command line arguments and their corresponding pytest.ini configure options
  are now respected (making it possible to have different format and logging
  levels in the log file than then console).
- A new log level called ``CONSOLE`` has been added between the default
  ``INFO`` and ``DEBUG`` levels. This level will show all reads and writes made
  to the serial console during testing.

Bug fixes in 24.0
~~~~~~~~~~~~~~~~~

Breaking changes in 24.0
~~~~~~~~~~~~~~~~~~~~~~~~~
- The `StepReporter` API has been changed. To start step reporting, you must
  now call ``StepReporter.start()`` instead of ``StepReporter()``
- Logging output when running pytest is no longer sent to stderr by default,
  since this is both chatty and also unnecessary with the improved logging
  flexibility. It it recommended to use the ``--log-cli-level=INFO`` command
  line option, or ``log_cli_level = INFO`` option in pytest.ini, but if you
  want to restore the old behavior add the following to your ``conftest.py``
  file (note that doing so may affect the ability to use some more advanced
  logging features)::

     def pytest_configure(config):
         import logging
         import sys

         logging.basicConfig(
             level=logging.INFO,
             format='%(levelname)8s: %(message)s',
             stream=sys.stderr,
         )

- The interpretation of the ``-v`` command line argument to pytest has changed
  slightly. ``-vv`` is now an alias for ``--log-cli-level=INFO`` (effectively
  unchanged), ``-vvv`` is an alias for ``--log-cli-level=CONSOLE``, and
  ``-vvvv`` is an alias for ``--log-cli-level=DEBUG``.

Known issues in 24.0
~~~~~~~~~~~~~~~~~~~~

Release 23.0 (Released Apr 24, 2023)
------------------------------------

New Features in 23.0
~~~~~~~~~~~~~~~~~~~~
- Python 3.6 support has been dropped.
- Exporter config templates now have access to the following new variables:
  isolated (all resource accesses must be tunneled True/False),
  hostname (of the exporter host), name (of the exporter).
- ModbusRTU driver for instruments
- Support for Eaton ePDU and TP-Link power strips added, either can be used as
  a NetworkPowerPort.
- The example strategies now wait for complete system startup using systemctl.
- Consider a combination of multiple "lg_feature" markers instead of
  considering only the closest marker.
- There is a new ``get_strategy`` helper function which returns the strategy of
  the target.
- labgrid-client now supports an ``export`` command which exposes the resource
  information as environment variables.
- Newer C920 webcams are now supported.
- The pytestplugin now correctly combines feature markers instead of replacing
  them.
- The ConsoleLoggingReporter is now exported for library usage.
- The HD 2MP Webcam is now supported by the video-driver.
- TP-Link power strips are supported by the NetworkPowerDriver.
- A ModbusRTUResource and Driver has been added to control RS485 equipment.
- The strategies within labgrid learned the force() function.
- The labgrid client SSH command is now able to instantiate the SSHDriver when
  there are multiple NetworkService resources available.
- eg_pms2_network power port driver supports controlling the Energenie power
  management series with devices like the EG_PMS2_LAN & EG_PMS2_WLAN.
- The client and coordinator learned of a new "release-from" operation that
  only releases a place if it acquired by a specific user. This can be used to
  prevent race conditions when attempting to automate the cleanup of unused
  places (e.g. in CI jobs).
- ModbusTCPCoil driver supports writing using multiple coils write method
  in order to make driver usable with Papouch Quido I/O modules.
- If supported, ser2net started by the exporter now allows multiple connections.
- SmallUBootDriver driver now supports wide range of Ralink/mt7621 devices
  which expects ``boot_secret`` without new line with new ``boot_secret_nolf``
  boolean config option.
- More USBVideo devices have been added.
- labgrid now uses a custom yaml loader/dumper.
- labgrid-client add-match/add-named-match check for duplicate matches
- `DFUDriver` has been added to communicate with a `DFUDevice`, a device in DFU
  (Device Firmware Upgrade) mode.
- ``labgrid-client dfu`` added to allow communication with devices in DFU mode.
- Support for QEMU Q35 machine added.
- `UBootDriver` now handles idle console, allowing driver activation on
  an interrupted U-Boot.
- Support for the STLINK-V3 has been added to the USBDebugger resource.
- labgrid-suggest can now suggest matches for a USBPowerPort used by power
  switchable USB hubs.
- AndroidFastboot is now deprecated and was replaced by AndroidUSBFastboot. This
  is more consistent with the AndroidNetFastboot support.
- In case multiple matches are found for a driver, labgrid-client now outputs
  the available names.
- ProcessWrapper now supports an "input" argument to check_output() that allows
  a string to be passed to stdin of the process.
- The ``NetworkInterfaceDriver`` now supports local and remote SSH port
  forwarding to/from the exporter.
- labgrid was switched over to use pyproject.toml.
- A contrib script was added to export coordinator metrics to stasd.
- The SSH connection timeout can now be globally controlled using the
  ``LG_SSH_CONNECT_TIMEOUT`` environment variable.
- The `QEMUDriver` now supports a ``display`` option which can specify if an
  display device should be created. ``none`` (the default) will not create a
  display device, ``fb-headless`` will create a headless framebuffer device
  for software rendering, and ``egl-headless`` will create a headless GPU
  device for accelerated rendering (but requires host support).
- The `AndroidFastbootDriver` now supports interaction with network devices in
  fastboot state.
- Add bash completion for labgrid-client.
- The `QEMUDriver` now support a ``nic`` property that can be used to create a
  network interface when booting.
- The SSHDriver now correctly uses the processwrapper for rsync.
- The `QEMUDriver` now supports API to add port-forwarding from localhost.
- The get() method for sdwire has been added.
- If there are multiple named resources for a target, one of them can be named
  "default" to select it automatically if no explicit other name is given.
- labgrid-client has been extended with --name/-n for most commands. This allows
  attaching multiple power sources/usb-muxes and switching them individually
  from the command line.
- Add DediprogFlashDriver and DediprogFlasher resource.
- Add support for Digital Loggers PDU.
- Add support for Shelly power switches.
- Make labgrid-client use crossbar_url and crossbar_realm from ennvironment
  config.

Bug fixes in 23.0
~~~~~~~~~~~~~~~~~

- The exporter now exports sysfsgpios during place acquire/release, fixing a
  race in the sysfspgio agent interface.
- Fixed a bug where using ``labgrid-client io get`` always returned ``low``
  when reading a ``sysfsgpio``.
- Fix labgrid-client exit code on keyboard interrupt.
- Fixed ``labgrid-client forward --remote``/``-R``, which used either the LOCAL
  part of ``--local``/``-L`` accidentally (if specified) or raised an
  UnboundLocalError.
- Fix udev matching by attributes.
- Stop Exporter's event loop when register calls fail.
- Fix exit codes for various subcommands.
- Omit role and place output for ``labgrid-client reserve`` to fix shell
  evaluation.

Breaking changes in 23.0
~~~~~~~~~~~~~~~~~~~~~~~~~
- ``Config``'s ``get_option()``/``get_target_option()`` convert non-string
  options no longer to strings.
- `UBootDriver`'s ``boot_expression`` attribute is deprecated, it will no
  longer check for the string during U-Boot boot. This allows activating the
  driver on an already running U-Boot.
- The uuu command handling was fixed for the UUUDriver.
- `UBootDriver` boot() method was fixed.
- Fix proxying of dynamic port power backends with URL in host parameter and
  authentication credentials.
- The coordinator was switched over to anonymous static authentication. You'll
  have to use the legacy crossbar configuration to support older
  clients/exporters. The 23.1 release will remove support for the legacy ticket
  authentication.
- AndroidFastboot has been deprecated. Please replace it with the more specific
  AndroidUSBFastboot with the same semantics.

Known issues in 23.0
~~~~~~~~~~~~~~~~~~~~

Release 0.4.0 (Released Sep 22, 2021)
-------------------------------------

New Features in 0.4.0
~~~~~~~~~~~~~~~~~~~~~

- Duplicate bindings for the same driver are now allowed (see the QEMUDriver)
- The `NetworkPowerDriver` now additionally supports:
  - Siglent SPD3000X series power supplies
- Labgrid client lock now enforces that all matches need to be fulfilled.
- Support for USB HID relays has been added.
- UBootDriver now allows overriding of currently fixed await boot timeout
  via new ``boot_timeout`` argument.
- With ``--lg-colored-steps``, two new ``dark`` and ``light`` color schemes
  which only use the standard 8 ANSI colors can be set in ``LG_COLOR_SCHEME``.
  The existing color schemes have been renamed to ``dark-256color`` and ``light-256color``.
  Also, the ``ColoredStepReporter`` now tries to autodetect whether the terminal
  supports 8 or 256 colors, and defaults to the respective dark variant.
  The 256-color schemes now use purple instead of green for the ``run`` lines to
  make them easier distinguishable from pytest's "PASSED" output.
- Network controlled relay providing GET/PUT based REST API
- The QEMUDriver gains support for -bios and qcow2 images.
- Support for audio input has been added.
- Usage of sshpass for SSH password input has been replaced with the SSH_ASKPASS
  environment variable.
- Labgrid supports the Linux Automation GmBH USB Mux now.
- NetworkManager control support on the exporter has been added. This allows
  control of bluetooth and wifi connected to the exporter.
- TFTP-/NFS-/HTTPProvider has been added, allowing easy staging of files for the
  DUT to later retrieve.
- Improved LG_PROXY documentation in docs/usage.rst.
- Exporter now checks /usr/sbin/ser2net for SerialPortExport
- Support for Tasmota-flashed power outlets controlled via MQTT has been added.
- The OpenOCDDriver has been reworked with new options and better output.
- A script to synchronize places to an external description was added.
- ShellDriver has regained the support to retrieve the active interface and IP
  addresses.
- Labgrid has gained support for HTTP Video streams.
- A settle time for the ShellDriver has been added to wait for chatty systems to
  settle before interacting with the shell.
- Support for Macrosilicon HDMI to USB (MJPEG) adapters was added.
- Console logfiles can now be created by the labgrid client command.
- A ManualSwitchDriver has been added to prompt the user to flip a switch or set
  a jumper.
- AndroidFastbootDriver now supports booting/flashing images preconfigured in
  the environment configuration.

Bug fixes in 0.4.0
~~~~~~~~~~~~~~~~~~
- ``pytest --lg-log foobar`` now creates the folder ``foobar`` before trying to
  write the log into it, and error handling was improved so that all possible
  errors that can occur when opening the log file are reported to stderr.
- gstreamer log messages are now suppressed when using labgrid-client video.
- Travis CI has been dropped for Github Actions.

Breaking changes in 0.4.0
~~~~~~~~~~~~~~~~~~~~~~~~~
- ``EthernetInterface`` has been renamed to ``NetworkInterface``.

Known issues in 0.4.0
~~~~~~~~~~~~~~~~~~~~~~~~~
- Some client commands return 0 even if the command failed.
- Currently empty passwords are not well supported by the ShellDriver

Release 0.3.0 (released Jan 22, 2021)
-------------------------------------

New Features in 0.3.0
~~~~~~~~~~~~~~~~~~~~~

- All `CommandProtocol` drivers support the poll_until_success method.
- The new `FileDigitalOutputDriver` represents a digital signal with a file.
- The new `GpioDigitalOutputDriver` controls the state of a GPIO via the sysfs interface.
- Crossbar and autobahn have been updated to 19.3.3 and 19.3.5 respectively.
- The InfoDriver was removed. The functions have been integrated into the
  labgridhelper library, please use the library for the old functionality.
- labgrid-client ``write-image`` subcommand: labgrid client now has a
  ``write-image`` command to write images onto block devices.
- ``labgrid-client ssh`` now also uses port from NetworkService resource if
  available
- The ``PLACE`` and ``STATE`` variables used by labgrid-client are replaced by
  ``LG_PLACE`` and ``LG_STATE``, the old variables are still supported for the
  time being.
- The SSHDriver's keyfile attribute is now specified relative to the config
  file just like the images are.
- The ShellDriver's keyfile attribute is now specified relative to the config
  file just like the images are.
- ``labgrid-client -P <PROXY>`` and the ``LG_PROXY`` environment variable can be
  used to access the coordinator and network resources via that SSH proxy host.
  Drivers which run commands via SSH to the exporter still connect directly,
  allowing custom configuration in the user's ``.ssh/config`` as needed.
  Note that not all drivers have been updated to use the ProxyManager yet.
- Deditec RELAIS8 devices are now supported by the `DeditecRelaisDriver`.
- The `RKUSBDriver` was added to support the rockchip serial download mode.
- The `USBStorageDriver` gained support for BMAP.
- Flashrom support added, by hard-wiring e.g. an exporter to the DUT, the ROM
  on the DUT can be written directly. The flashrom driver implements the
  bootstrap protocol.
- AndroidFastbootDriver now supports 'getvar' and 'oem getenv' subcommands.
- The coordinator now updates the resource acquired state at the exporter.
  Accordingly, the exporter now starts ser2net only when a resources is
  acquired. Furthermore, resource conflicts between places are now detected.
- Labgrid now uses the `ProcessWrapper` for externally called processes. This
  should include output from these calls better inside the test runs.
- The binding dictionary can now supports type name strings in addition to the
  types themselves, avoiding the need to import a specific protocol or driver
  in some cases.
- The remote infrastructure gained support for place reservations, for further
  information check the section in the documentation.
- The `SigrokDriver` gained support for the Manson HCS-2302, it allows enabling
  and disabling channels, measurement and setting the current and voltage limit.
- ``labgrid-client write-image`` gained new arguments: ``--partition``,
  ``--skip``, ``--seek``.
- Support for Sentry PDUs has been added.
- Strategies now implement a ``force`` method, to ``force`` a strategy state
  irrespective of the current state.
- SSH Connections can now be proxied over the exporter, used by adding a device
  suffix to the `NetworkService` address.
- UBootDriver now allows overriding of default boot command (``run bootcmd``)
  via new ``boot_command`` argument.
- The config file supports per-target options, in addition to global options.
- Add power driver to support GEMBIRD SiS-PM implementing SiSPMPowerDriver.
- A cleanup of the cleanup functions was performed, labgrid should now clean up
  after itself and throws an error if the user needs to handle it himself.
- ``labgrid-client`` now respects the ``LG_HOSTNAME`` and ``LG_USERNAME``
  environment variables to set the hostname and username when accessing
  resources.
- PyVISA support added, allowing to use PyVISA controlled test equipment from
  Labgrid.
- ``labgrid-client write-image`` gained a new argument ``--mode`` to specify
  which tool should be used to write the image (either ``dd`` or ``bmaptool``)
- Exporter configuration file ``exporter.yaml`` now allows use of environment
  variables.

Breaking changes in 0.3.0
~~~~~~~~~~~~~~~~~~~~~~~~~
- `ManagedFile` now saves the files in a different directory on the exporter.
  Previously ``/tmp`` was used, labgrid now uses ``/var/cache/labgrid``.
  A tmpfiles example configuration for systemd is provided in the ``/contrib``
  directory.
  It is also highly recommended to enable ``fs.protected_regular=1`` and
  ``fs.protected_fifos=1`` for kernels>=4.19.
  This requires user intervention after the upgrade to create the directory and
  setup the cleanup job.
- ``@attr.s(cmp=False)`` is deprecated and all classes have been moved to
  ``@attr.s(eq=False)``, this release requires attrs version 19.2.0
- Coordinator work dir is now set to the same dir as the crossbar configuration
  dir. Hence coordinator specific files like ``places.yaml`` and
  ``resources.yaml`` are now also stored in the crossbar configuration folder.
  Previously it would use ``..``.
- The ``HawkbitTestClient`` and ``USBStick`` classes have been removed
- The original USBStorageDriver was removed, ``NetworkUSBStorageDriver`` was
  renamed to `USBStorageDriver`.
  A deprecated `NetworkUSBStorageDriver` exists temporarily for compatibility
  reasons.

Known issues in 0.3.0
~~~~~~~~~~~~~~~~~~~~~~~~~
- There are several reports of ``sshpass`` used within the SSHDriver not working
  in call cases or only on the first connection.
- Some client commands return 0 even if the command failed.
- Currently empty passwords are not well supported by the ShellDriver

Release 0.2.0 (released Jan 4, 2019)
------------------------------------

New Features in 0.2.0
~~~~~~~~~~~~~~~~~~~~~

- A colored StepReporter was added and can be used with ``pytest
  --lg-colored-steps``.
- ``labgrid-client`` can now use the last changed information to sort listed
  resources and places.
- ``labgrid-client ssh`` now uses ip/user/password from NetworkService resource
  if available
- The pytest plugin option ``--lg-log`` enables logging of the serial traffic
  into a file (see below).
- The environement files can contain feature flags which can be used to control
  which tests are run in pytest.
- ``LG_*`` variables from the OS environment can be used in the config file with
  the ``!template`` directive.
- The new "managed file" support takes a local file and synchronizes it to a
  resource on a remote host. If the resource is not a `NetworkResource`, the
  local file is used instead.
- ProxyManager: a class to automatically create ssh forwardings to proxy
  connections over the exporter
- SSHManager: a global manager to multiplex connections to different exporters
- The target now saves it's attached drivers, resources and protocols in a
  lookup table, avoiding the need of importing many Drivers and Protocols (see
  `Syntactic sugar for Targets`_)
- When multiple Drivers implement the same Protocol, the best one can be
  selected using a priority (see below).
- The new subcommand ``labgrid-client monitor`` shows resource or places
  changes as they happen, which is useful during development or debugging.
- The environment yaml file can now list Python files (under the 'imports' key).
  They are imported before constructing the Targets, which simplifies using
  custom Resources, Drivers or Strategies.
- The pytest plugin now stores metadata about the environment yaml file in the
  junit XML output.
- The ``labgrid-client`` tool now understands a ``--state`` option to
  transition to the provided state using a :any:`Strategy`.
  This requires an environment yaml file with a :any:`RemotePlace` Resources and
  matching Drivers.
- Resource matches for places configured in the coordinator can now have a
  name, allowing multiple resources with the same class.
- The new `Target.__getitem__` method makes writing using protocols less verbose.
- Experimental: The labgrid-autoinstall tool was added (see below).

New and Updated Drivers
~~~~~~~~~~~~~~~~~~~~~~~

- The new `DigitalOutputResetDriver` adapts a driver implementing the
  DigitalOutputProtocol to the ResetProtocol.
- The new `ModbusCoilDriver` support outputs on a ModbusTCP device.
- The new ``NetworkUSBStorageDriver`` allows writing to remote USB storage
  devices (such as SD cards or memory sticks connected to a mux).
- The new `QEMUDriver` runs a system image in QEmu and implements the
  :any:`ConsoleProtocol` and :any:`PowerProtocol`.
  This allows using labgrid without any real hardware.
- The new `QuartusHPSDriver` controls the "Quartus Prime Programmer and Tools"
  to flash a target's QSPI.
- The new `SerialPortDigitalOutputDriver` controls the state of a GPIO using
  the control lines of a serial port.
- The new `SigrokDriver` uses a (local or remote) device supported by sigrok to
  record samples.
- The new `SmallUBootDriver` supports the extremely limited U-Boot found in
  cheap WiFi routers.
- The new `USBSDMuxDriver` controls a Pengutronix USB-SD-Mux device.
- The new `USBTMCDriver` can fetch measurements and screenshots from the
  "Keysight DSOX2000 series" and the "Tektronix TDS 2000 series".
- The new `USBVideoDriver` can stream video from a remote H.264
  UVC (USB Video Class) camera using gstreamer over SSH. Currently,
  configuration for the "Logitech HD Pro Webcam C920" exists.
- The new `XenaDriver` allows interacting with Xena network testing equipment.
- The new `YKUSHPowerDriver` and `USBPowerDriver` support software-controlled
  USB hubs.
- The bootloader drivers now have a ``reset`` method.
- The `BareboxDriver`'s boot string is now configurable, which allows it to work
  with the ``quiet`` Linux boot parameter.
- The `IMXUSBLoader` now recognizes more USB IDs.
- The `OpenOCDDriver` is now more flexible with loading configuration files.
- The `NetworkPowerDriver` now additionally supports:

  - 24 port "Gude Expert Power Control 8080"
  - 8 port "Gude Expert Power Control 8316"
  - NETIO 4 models (via telnet)
  - a simple REST interface

- The `SerialDriver` now supports using plain TCP instead of RFC 2217, which is
  needed from some console servers.
- The `ShellDriver` has been improved:
  
  - It supports configuring the various timeouts used during the login process.
  - It can use xmodem to transfer file from and to the target.

Incompatible Changes
~~~~~~~~~~~~~~~~~~~~

- When using the coordinator, it must be upgrade together with the clients
  because of the newly introduce match names.
- Resources and Drivers now need to be created with an explicit name
  parameter.
  It can be ``None`` to keep the old behaviour.
  See below for details.
- Classes derived from :any:`Resource` or :any:`Driver` now need to use
  ``@attr.s(cmp=False)`` instead of ``@attr.s`` because of a change in the
  attrs module version 17.1.0.

Syntactic sugar for Targets
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Targets are now able to retrieve requested drivers, resources or protocols by
name instead of by class.
This allows removing many imports, e.g.

::

   from labgrid.driver import ShellDriver

   shell = target.get_driver(ShellDriver)

becomes

::

   shell = target.get_driver("ShellDriver")

Also take a look at the examples, they have been ported to the new syntax as well.

Multiple Driver Instances
~~~~~~~~~~~~~~~~~~~~~~~~~

For some Protocols, it is useful to allow multiple instances.

DigitalOutputProtocol:
   A board may have two jumpers to control the boot mode in addition to a reset
   GPIO.
   Previously, it was not possible to use these on a single target.

ConsoleProtocol:
   Some boards have multiple console interfaces or expose a login prompt via a
   USB serial gadget.

PowerProtocol:
   In some cases, multiple power ports need to be controlled for one Target.

To support these use cases, Resources and Drivers must be created with a
name parameter.
When updating your code to this version, you can either simply set the name to
``None`` to keep the previous behaviour.
Alternatively, pass a string as the name.

Old:

.. code-block:: python

  >>> t = Target("MyTarget")
  >>> SerialPort(t)
  SerialPort(target=Target(name='MyTarget', env=None), state=<BindingState.bound: 1>, avail=True, port=None, speed=115200)
  >>> SerialDriver(t)
  SerialDriver(target=Target(name='MyTarget', env=None), state=<BindingState.bound: 1>, txdelay=0.0)

New (with name=None):

.. code-block:: python

  >>> t = Target("MyTarget")
  >>> SerialPort(t, None)
  SerialPort(target=Target(name='MyTarget', env=None), name=None, state=<BindingState.bound: 1>, avail=True, port=None, speed=115200)
  >>> SerialDriver(t, None)
  SerialDriver(target=Target(name='MyTarget', env=None), name=None, state=<BindingState.bound: 1>, txdelay=0.0)

New (with real names):

.. code-block:: python

  >>> t = Target("MyTarget")
  >>> SerialPort(t, "MyPort")
  SerialPort(target=Target(name='MyTarget', env=None), name='MyPort', state=<BindingState.bound: 1>, avail=True, port=None, speed=115200)
  >>> SerialDriver(t, "MyDriver")
  SerialDriver(target=Target(name='MyTarget', env=None), name='MyDriver', state=<BindingState.bound: 1>, txdelay=0.0)

Priorities
~~~~~~~~~~

Each driver supports a priorities class variable.
This allows drivers which implement the same protocol to add a priority option
to each of their protocols.
This way a `NetworkPowerDriver` can implement the `ResetProtocol`, but if another
`ResetProtocol` driver with a higher protocol is available, it will be selected
instead.
See the documentation for details.

ConsoleLogging Reporter
~~~~~~~~~~~~~~~~~~~~~~~

The ConsoleLoggingReporter can be used with the pytest plugin or the library.
It records the Data send from a DUT to the computer running labgrid.
The logfile contains a header with the name of the device from the environment
configuration and a timestamp.

When using the library, the reporter can be started with::

  from labgrid.consoleloggingreporter import ConsoleLoggingReporter

  ConsoleLoggingReporter.start(".")

where "." is the output directory.

The pytest plugin accepts the ``--lg-log`` commandline option, either with or
without an output path.

Auto-Installer Tool
~~~~~~~~~~~~~~~~~~~

To simplify using labgrid for provisioning several boards in parallel, the
``labgrid-autoinstall`` tool was added.
It reads a YAML file defining several targets and a Python script to be run for
each board.
Interally, it spawns a child process for each target, which waits until a matching
resource becomes available and then executes the script.

For example, this makes it simple to load a bootloader via the
:any:`BootstrapProtocol`, use the :any:`AndroidFastbootDriver` to upload a
kernel with initramfs and then write the target's eMMC over a USB Mass Storage
gadget.

.. note::
  ``labgrid-autoinstall`` is still experimental and no documentation has been written.

Contributions from: Ahmad Fatoum, Bastian Krause, Björn Lässig, Chris Fiege, Enrico Joerns, Esben Haabendal, Felix Lampe, Florian Scherf, Georg Hofmann, Jan Lübbe, Jan Remmet, Johannes Nau, Kasper Revsbech, Kjeld Flarup, Laurentiu Palcu, Oleksij Rempel, Roland Hieber, Rouven Czerwinski, Stanley Phoong Cheong Kwan, Steffen Trumtrar, Tobi Gschwendtner, Vincent Prince

Release 0.1.0 (released May 11, 2017)
-------------------------------------

This is the initial release of labgrid.
