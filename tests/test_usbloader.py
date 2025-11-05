import pytest

from labgrid.resource.udev import SamsungUSBLoader, SunxiUSBLoader
from labgrid.resource.udev import TegraUSBLoader
from labgrid.resource.remote import NetworkSamsungUSBLoader
from labgrid.resource.remote import NetworkSunxiUSBLoader
from labgrid.resource.remote import NetworkTegraUSBLoader
from labgrid.driver.usbloader import SamsungUSBDriver, SunxiUSBDriver
from labgrid.driver.usbloader import TegraUSBDriver


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


def test_tegrausb_network_create(target):
    r = NetworkTegraUSBLoader(target, busnum=1, devnum=2, path='a/path',
                                vendor_id=1234, model_id=5678, name=None,
                                host='localhost')
    assert isinstance(r, NetworkTegraUSBLoader)
    assert r.busnum == 1
    assert r.devnum == 2
    assert r.path == 'a/path'
    assert r.vendor_id == 1234
    assert r.model_id == 5678
    assert r.name is None
    d = TegraUSBDriver(target, loadaddr=0x100, bct='bct', usb_path='3/4',
                       name=None)
    assert isinstance(d, TegraUSBDriver)
    assert d.loadaddr == 0x100
    assert d.name is None


def test_tegrausb_driver_create(target):
    r = TegraUSBLoader(target, name=None)
    assert isinstance(r, TegraUSBLoader)

    d = TegraUSBDriver(target, loadaddr=0x100, bct='bct', usb_path='3/4',
                       name=None)
    assert isinstance(d, TegraUSBDriver)


def test_tegrausb_driver_load(target, mocker, tmpdir):
    r = TegraUSBLoader(target, name=None)
    assert isinstance(r, TegraUSBLoader)

    d = TegraUSBDriver(target, loadaddr=0x100, bct='bct', usb_path='3/4',
                       name=None)
    r.avail = True
    dev = FakeDevice()
    r.device = dev
    target.activate(d)

    main = tmpdir.join('boot').strpath
    with open(main, 'wb') as outf:
        outf.write(b'main image')

    pwrap = mocker.patch('labgrid.driver.usbloader.processwrapper')

    pwrap.reset_mock()
    d.load(main)
    pwrap.check_output.assert_called_once_with(
        ['tegrarcm', '--bct=bct', f'--bootloader={main}', '--loadaddr=0x000100',
         '--usb-port-path', '3/4'], print_on_silent_log=True)


def test_samsungusb_network_create(target):
    r = NetworkSamsungUSBLoader(target, busnum=1, devnum=2, path='a/path',
                                vendor_id=1234, model_id=5678, name=None,
                                host='localhost')
    assert isinstance(r, NetworkSamsungUSBLoader)
    assert r.busnum == 1
    assert r.devnum == 2
    assert r.path == 'a/path'
    assert r.vendor_id == 1234
    assert r.model_id == 5678
    assert r.name is None
    d = SamsungUSBDriver(target, bl1='bl1', bl1_loadaddr=0x100,
                         spl_loadaddr=0x200, loadaddr=0x300, name=None)
    assert isinstance(d, SamsungUSBDriver)
    assert d.bl1 == 'bl1'
    assert d.bl1_loadaddr == 0x100
    assert d.spl_loadaddr == 0x200
    assert d.loadaddr == 0x300
    assert d.name is None


def test_samsungusb_driver_create(target):
    r = SamsungUSBLoader(target, name=None)
    assert isinstance(r, SamsungUSBLoader)

    d = SamsungUSBDriver(target, bl1='bl1', bl1_loadaddr=0x100,
                         spl_loadaddr=0x200, loadaddr=0x300, name=None)
    assert isinstance(d, SamsungUSBDriver)


def test_samsungusb_driver_load(target, mocker, tmpdir):
    r = SamsungUSBLoader(target, name=None)
    assert isinstance(r, SamsungUSBLoader)

    bl1 = tmpdir.join('bl1').strpath
    d = SamsungUSBDriver(target, bl1=bl1, bl1_loadaddr=0x100,
                         spl_loadaddr=0x200, loadaddr=0x300, name=None)
    r.avail = True
    dev = FakeDevice()
    r.device = dev
    target.activate(d)

    with open(bl1, 'wb') as outf:
        outf.write(b'blah')

    pwrap = mocker.patch('labgrid.driver.usbloader.processwrapper')

    d.load(phase='bl1')
    pwrap.check_output.assert_called_once_with(
        ['smdk-usbdl', '-a', '100', '-b', '001', '-d', '002', '-f', bl1])
