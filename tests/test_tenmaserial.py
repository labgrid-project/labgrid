from labgrid.resource.remote import NetworkTenmaSerialPort
from labgrid.driver.powerdriver import TenmaSerialDriver

def test_tenmaserial_create(target):
    r = NetworkTenmaSerialPort(target,
            name=None,
            host="localhost",
            busnum=0,
            devnum=1,
            path='0:1',
            vendor_id=0x0,
            model_id=0x0,
            index=1,
    )
    d = TenmaSerialDriver(target, name=None)
    assert (isinstance(d, TenmaSerialDriver))
