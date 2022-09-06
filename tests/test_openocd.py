import pytest
from shutil import which
import subprocess

from labgrid.resource.udev import USBDebugger
from labgrid.driver.openocddriver import OpenOCDDriver


pytestmark = pytest.mark.skipif(not which("openocd"),
                              reason="openocd not available")


def test_openocd_resource(target):
    r = USBDebugger(target, name=None, match={"sys_name": "1-12"})


def test_openocd_driver_activate(target):
    r = USBDebugger(target, name=None, match={"sys_name": "1-12"})
    r.avail = True
    d = OpenOCDDriver(target, name=None)
    target.activate(d)


def test_openocd_driver(target, tmpdir):
    r = USBDebugger(target, name=None, match={"sys_name": "1-12"})
    r.avail = True
    d = OpenOCDDriver(target, name=None, load_commands=["shutdown"])
    target.activate(d)
    d.load(__file__)

    with pytest.raises(subprocess.CalledProcessError):
        d.execute(["invalid_command_labgrid"])

    d.execute(["shutdown"])
