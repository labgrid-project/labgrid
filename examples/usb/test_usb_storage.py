from labgrid.resource.udev import USBMassStorage
from labgrid.driver import USBStorageDriver

def test_usb_storage(target):
    r = target.get_resource(USBMassStorage)
    assert r.path is not None

def test_usb_storage_size(target):
    d = target.get_driver(USBStorageDriver)
    assert d.get_size() > 0
