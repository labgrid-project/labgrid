from labgrid.resource.remote import NetworkUSBTMC
from labgrid.driver.usbtmcdriver import USBTMCDriver


def test_usbtmc_create(target):
    r = NetworkUSBTMC(target,
            name=None,
            host="localhost",
            busnum=0,
            devnum=1,
            path='/dev/usbtmc0',
            vendor_id=0x0,
            model_id=0x0,
    )
    d = USBTMCDriver(target, name=None)
    assert (isinstance(d, USBTMCDriver))

def test_import_backends():
    import labgrid.driver.usbtmc.keysight_dsox2000
