import pytest
import os.path
from time import sleep
from shutil import which

from labgrid.resource.udev import SigrokUSBDevice, SigrokUSBSerialDevice
from labgrid.resource.sigrok import SigrokDevice
from labgrid.driver.sigrokdriver import SigrokDriver, SigrokPowerDriver


pytestmark = pytest.mark.skipif(not which("sigrok-cli"),
                              reason="sigrok not available")


def test_sigrok_resource(target):
    r = SigrokUSBDevice(target, name=None, match={"sys_name": "1-12"}, driver='fx2lafw', channels="D0,D1")


def test_sigrok_driver(target):
    r = SigrokDevice(target, name=None, driver='demo', channels="D0")
    d = SigrokDriver(target, name=None)
    target.activate(d)


@pytest.mark.sigrokusb
def test_sigrok_usb_driver(target, tmpdir):
    r = SigrokUSBDevice(target, name=None, match={"ID_MODEL_ID": "3881", "ID_VENDOR_ID": "0925"}, driver='fx2lafw', channels="D0,D1")
    d = SigrokDriver(target, name=None)
    target.activate(d)
    record = tmpdir.join("output.sr")
    d.capture(record)
    sleep(5)
    samples = d.stop()
    assert os.path.getsize(record) > 0
    assert samples != None
    assert list(samples[0].keys()) == ['time', 'D0', 'D1']
    assert list(samples[-1].keys()) == ['time', 'D0', 'D1']

def test_sigrok_power_driver(target):
    r = SigrokUSBSerialDevice(target, name=None, driver='manson-hcs-3xxx')
    r.avail = True
    d = SigrokPowerDriver(target, name=None)
    target.activate(d)
