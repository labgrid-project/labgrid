from labgrid.resource.remote import NetworkUSBVideo
from labgrid.driver.usbvideodriver import USBVideoDriver


def test_usbvideo_create(target):
    r = NetworkUSBVideo(target,
            name=None,
            host="localhost",
            busnum=0,
            devnum=1,
            path='0:1',
            vendor_id=0x0,
            model_id=0x0,
    )
    d = USBVideoDriver(target, name=None)
    assert (isinstance(d, USBVideoDriver))

