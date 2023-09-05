# Lauterbach TRACE32 Example

labgrid can integrate a Lauterbach debugger to automate the board bring-up.
Although this example was tested with Zephyr OS, a BlackPill Board and a Lauterbach PowerDebug X50,
it can be adapted for other supported boards [^1]
and other Lauterbach debugger models or TRACE32 releases.
An LXA TAC [^2] was used to make resource available at the remote location.

- [Prerequisites](#prerequisites)
- [Build Steps](#build-steps)
- [Hardware Setup](#hardware-setup)
- [Files](#files)
- [Configuration](#configuration)
- [Run Test Suite with Local Environment](#run-test-suite-with-local-environment)
- [Run Test Suite with Remote Environment](#run-test-suite-with-remote-environment)
- [Run Library Example](#run-library-example)

## Prerequisites

To build and run the example these hardware and software components are required:
  - Zephyr OS
    [3.5.0](https://github.com/zephyrproject-rtos/zephyr/releases/tag/v3.5.0)
  - Zephyr OS [Developer Docker Image](https://github.com/zephyrproject-rtos/docker-image) v0.26.6
  - [WeAct Studio BlackPill
    Board](https://github.com/WeActStudio/WeActStudio.BlackPill) with *STM32F411CE*
  - USB to serial UART bridge
  - Lauterbach PowerDebug X50
  - TRACE32 Release R.2025.02

## Build Steps

Get the Zephyr source code and set up the Zephyr Developer Container Image,
so that Zephyr sample applications can be build.
The application for our *STM32F411CE* is based on the [UART echo](https://docs.zephyrproject.org/latest/samples/drivers/uart/echo_bot/README.html) sample.
A slight modification of the sample code allows us to trigger a fatal error via the UART serial interface,
if the string `"PANIC"` is received.

1. Mount your local Zephyr workspace into the container and start a terminal
```bash
docker run -ti -v <local-zephyr-workspace>:/workdir ghcr.io/zephyrproject-rtos/zephyr-build:v0.26.6
```
2. Switch to the directory `zephyr`
```
cd /workdir/zephyr
```
3. Apply this patch to `samples/drivers/uart/echo_bot/src/main.c`:
```diff
@@ -102,6 +102,9 @@ int main(void)
                print_uart("Echo: ");
                print_uart(tx_buf);
                print_uart("\r\n");
+
+               if (strcmp(tx_buf, "PANIC") == 0)
+                       k_oops();
        }
        return 0;
 }
```

4. Apply this patch to `samples/drivers/uart/echo_bot/prj.conf`:
```diff
@@ -1,2 +1,12 @@
 CONFIG_SERIAL=y
 CONFIG_UART_INTERRUPT_DRIVEN=y
+CONFIG_INIT_STACKS=y
+CONFIG_THREAD_STACK_INFO=y
+CONFIG_TRACING_STACK=y
+CONFIG_TRACING=y
+CONFIG_TRACING_OBJECT_TRACKING=y
+CONFIG_PM=y
+CONFIG_PM_DEVICE=y
+CONFIG_PM_DEVICE_RUNTIME=n
+CONFIG_PM_DEVICE_RUNTIME_EXCLUSIVE=n
+CONFIG_DEBUG=y
```

5. Build the [UART echo bot](https://docs.zephyrproject.org/latest/samples/drivers/uart/echo_bot/README.html) sample application:
```
west build --board blackpill_f411ce samples/drivers/uart/echo_bot
```

## Hardware Setup

Connect the `TX` (`A9`) and `RX` (`A10`) on the BlackPill board to the USB to UART bridge
to make the serial interface accessible.
Wire the `3V3`, `GND`, `SCK`, and `DIO` pins on the BlackPill SWD header to the [IDC20A](https://repo.lauterbach.com/adidc20a.html) pinout.
It is recommended to connect the reset line `R`, too.
Get the device name of the Lauterbach X50 by starting TRACE32 and entering the command `IFCONFIG`.

## Files

**blackpill.cmm**
PRACTICE script that flashes the board,
sets up the serial interface connection
and runs the boot steps.

**library.py**
Python script that demonstrates how to use labgrid/`LauterbachDriver` as a libary and
the Remote API for command injection and status checks.

**local.yaml**
Environment configuration for a `NetworkLauterbachDebugger` available on the local network.

**remote.yaml**
Environment configuration for a remote location with `NetworkLauterbachDebugger`,
power port
and serial interface.

**remote_usb.yaml**
Environment configuration for a remote location with `USBLauterbachDebugger`,
power port
and serial interface.
The PowerDebug module is connected to the remote computer via USB.

**test_local.py**
`pytest` test suite that uses the Remote API to check stack consumption
and ramdump generation.

**test_remote.py**
`pytest` test suite that flashes a new target image
and then checks the serial port for the boot notification.

## Configuration

The files `blackpill.cmm` and `test_remote.py` assume that the Zephyr sample application can be found at `<workdir>/zephyr/build/zephyr/zephyr.elf`.
The path prefix `<workdir>` can be changed in `blackpill.cmm` via the PRACTICE macro `&workdir`
and in `test_remote.py` via the constant `WORKDIR`:
```diff
@@ -8,7 +8,7 @@ PRIVATE &labgrid &elf &term &workdir
 &labgrid=STRing.SCANAndExtract("&param","LABGRID_COMMAND=","")
 &elf=STRing.SCANAndExtract("&param","FILE=","")
 &term=STRing.SCANAndExtract("&param","TERM=","OFF")
-&workdir=STRing.SCANAndExtract("&param","WORKDIR=","~/workspace/zephyrproject")
+&workdir=STRing.SCANAndExtract("&param","WORKDIR=","~/workspace/your-special-folder")
```

```diff
@@ -2,7 +2,7 @@ import os

 import pytest

-WORKDIR = os.path.join("~", "workspace", "zephyrproject")
+WORKDIR = os.path.join("~", "workspace", "your-special-folder")
```

Before running the "local" test suite,
open the environment configuration `local.yaml`,
change the device name and select the TRACE32 installation directory:
```diff
targets:
  main:
    resources:
      NetworkLauterbachDebugger:
+        node: <your-device-name>
        protocol: TCP
    drivers:
      LauterbachDriver:
        enable_rcl: true
paths:
+  t32-dir: <your-t32-installation>
```

Before running the library example,
open the script `library.py`
and change the device name:
```diff
@@ -7,7 +7,7 @@ t = Target(name="main")
 x50 = NetworkLauterbachDebugger(
     t,
     name=None,
+    node="<your-device-name>",
     protocol="TCP"
 )
```

Before running the "remote" test suite,
create a `RemotePlace`
where the PowerDebug X50
and the USB to serial UART bridge are made available by the exporter.

Here is an exporter configuration snippet
that registers a PowerDebug module resource with Ethernet connection:
```yaml
demo2:
  t32:
    cls: NetworkLauterbachDebugger
    node: <your-device-name>
```
Replace `<your-device-name>` with the name of your device.

To use a PowerDebug module
that is connected to the exporter via USB,
use this snippet:
```yaml
demo3:
  t32:
    cls: USBLauterbachDebugger
```

## Run Test Suite with Local Environment

To execute the tests with `pytest`, run
```
pytest -v --lg-env local.yaml test_local.py
```

You should get output similar to the following:
```
=============================================================================================== test session starts =========================================================================
platform linux -- Python 3.12.3, pytest-8.4.0, pluggy-1.6.0 -- /home/csax/workspace/ltbgrid-integration/venv-dev_trace32_upstream_labgrid/bin/python3
cachedir: .pytest_cache
benchmark: 5.1.0 (defaults: timer=time.perf_counter disable_gc=False min_rounds=5 min_time=0.000005 max_time=1.0 calibration_precision=10 warmup=False warmup_iterations=100000)
rootdir: /home/csax/workspace/ltbgrid-integration/labgrid/examples
configfile: pytest.ini
plugins: mock-3.14.1, isort-4.0.0, cov-6.1.1, labgrid-25.1.dev1, benchmark-5.1.0, dependency-0.6.0, anyio-4.9.0
collected 2 items

test_local.py::test_stack PASSED                                                                                                                                                      [ 50%]
test_local.py::test_ramdump PASSED                                                                                                                                                    [100%]

=============================================================================================== 2 passed in 47.90s ==========================================================================
```

## Run Test Suite with Remote Environment

Depending on whether your PowerDebug module is connected via Ethernet or USB use either the environment configuration `remote.yaml` or `remote_usb.yaml`.

**Ethernet:**

 Run the command
```
pytest -v --lg-env remote.yaml test_remote.py
```

**USB:**

 Run the command
```
pytest -v --lg-env remote_usb.yaml test_remote.py
```

You should get output similar to the following:
```
=============================================================================================== test session starts =========================================================================
platform linux -- Python 3.12.3, pytest-8.4.0, pluggy-1.6.0 -- /home/csax/workspace/ltbgrid-integration/venv-dev_trace32_upstream_labgrid/bin/python3
cachedir: .pytest_cache
benchmark: 5.1.0 (defaults: timer=time.perf_counter disable_gc=False min_rounds=5 min_time=0.000005 max_time=1.0 calibration_precision=10 warmup=False warmup_iterations=100000)
rootdir: /home/csax/workspace/ltbgrid-integration/labgrid/examples
configfile: pytest.ini
plugins: mock-3.14.1, isort-4.0.0, cov-6.1.1, labgrid-25.1.dev1, benchmark-5.1.0, dependency-0.6.0, anyio-4.9.0
collected 1 item

test_remote.py::test_boot_status PASSED                                                                                                                                               [100%]

================================================================================================ 1 passed in 7.61s ==========================================================================
```


## Run Library Example

Run the command
```
python library.py
```

You should get output similar to the following:
```
Opening Remote API connection
Target halted at breakpoint
Remote API connection closed
```

[^1]: [Zephys OS Supported Boards](https://docs.zephyrproject.org/latest/boards/index.html)
[^2]: [LXA TAC manual](https://linux-automation.com/lxatac-M02/)
