import pytest

from labgrid.resource.udev import SunxiUSBLoader
from labgrid.resource.remote import NetworkSunxiUSBLoader
from labgrid.driver.usbloader import SunxiUSBDriver


class FakeDevice:
    """Fake USB device to use for testing"""
    subsystem = 'usb'
    device_type = 'usb_device'
    properties= {'BUSNUM': 1, 'DEVNUM': 2}


def test_sunxiusb_network_create(target):
    r = NetworkSunxiUSBLoader(target, busnum=1, devnum=2, path='a/path',
                                vendor_id=1234, model_id=5678, name=None,
                                host='localhost')
    assert isinstance(r, NetworkSunxiUSBLoader)
    assert r.busnum == 1
    assert r.devnum == 2
    assert r.path == 'a/path'
    assert r.vendor_id == 1234
    assert r.model_id == 5678
    assert r.name is None
    d = SunxiUSBDriver(target, loadaddr=0x100, name=None)
    assert isinstance(d, SunxiUSBDriver)
    assert d.loadaddr == 0x100
    assert d.name is None


def test_sunxiusb_driver_create(target):
    r = SunxiUSBLoader(target, name=None)
    assert isinstance(r, SunxiUSBLoader)

    d = SunxiUSBDriver(target, loadaddr=0x100, name=None)
    assert isinstance(d, SunxiUSBDriver)


def test_sunxiusb_driver_load(target, mocker, tmpdir):
    r = SunxiUSBLoader(target, name=None)
    assert isinstance(r, SunxiUSBLoader)

    d = SunxiUSBDriver(target, loadaddr=0x100, name=None)
    r.avail = True
    dev = FakeDevice()
    r.device = dev
    target.activate(d)

    spl = tmpdir.join('spl').strpath
    with open(spl, 'wb') as outf:
        outf.write(b'spl image')

    main = tmpdir.join('spl').strpath
    with open(spl, 'wb') as outf:
        outf.write(b'main image')

    pwrap = mocker.patch('labgrid.driver.usbloader.processwrapper')

    d.load(spl, phase='spl')
    pwrap.check_output.assert_called_once_with(
        ['sunxi-fel', '-d', '1:2', 'spl', spl], print_on_silent_log=True)

    pwrap.reset_mock()
    d.load(main)
    pwrap.check_output.assert_called_once_with(
        ['sunxi-fel', '-d', '1:2', 'write', '0x100', main], print_on_silent_log=True)
