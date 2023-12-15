import os
import pytest

from collections import namedtuple

from labgrid.driver.lauterbachdriver import LauterbachDriver
from labgrid.resource.udev import USBLauterbachDebugger
from labgrid.resource.lauterbach import NetworkLauterbachDebugger, RemoteUSBLauterbachDebugger
from labgrid.util.helper import get_uname_machine

pytest.importorskip("lauterbach.trace32.pystart")

PseudoUSBDevice = namedtuple("Device", ["sys_name", "sys_path", "subsystem", "device_type", "properties"])
PSEUDOUSB = PseudoUSBDevice("1-12", "/dev/null", "usb", "usb_device", {"BUSNUM" : "1", "DEVNUM" : "12"})

# for most of the tests it's enough to specify a valid directory
os.environ["T32SYS"] = os.environ.get("T32SYS", "/tmp")

def check_t32tcpusb_present():
    if get_uname_machine()!="amd64":
        return False
    tcpusb = os.path.join(os.environ["T32SYS"], "bin/pc_linux64/t32tcpusb")
    if not os.path.isfile(tcpusb):
        return False
    return True

def test_lauterbach_usb_resource(target):
    r = USBLauterbachDebugger(target, name=None, match={"sys_name": "1-12"})

def test_lauterbach_network_resource(target):
    r = NetworkLauterbachDebugger(target, name=None, node="test")

def test_lauterbach_usb_driver_activate(target):   
    r = USBLauterbachDebugger(target, name=None, match={"sys_name": "1-12"}, device=PSEUDOUSB)
    r.avail = True
    d = LauterbachDriver(target, name=None)
    target.activate(d)

    assert(d.connection)

    target.deactivate(d)

def test_lauterbach_network_driver_activate(target):
    r = NetworkLauterbachDebugger(target, name=None, node="test")
    r.avail = True
    d = LauterbachDriver(target, name=None)
    target.activate(d)

    assert(d.connection)

    target.deactivate(d)

@pytest.mark.skipif(not check_t32tcpusb_present(),
                    reason="t32tcpusb not installed on machine")
@pytest.mark.skipif(True, reason="don't know how to test NetworkUSB.. resources")
def test_lauterbach_networkusb_driver_activate(target):   
    r = RemoteUSBLauterbachDebugger(
            target,
            name=None,
            host="localhost",
            busnum=0,
            devnum=1,
            path='0:1',
            vendor_id=0x0,
            model_id=0x0
    )
    r.avail = True
    d = LauterbachDriver(target, name=None)
    target.activate(d)

    assert(d.connection)
    assert(d.t32tcpusb)
