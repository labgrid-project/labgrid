from labgrid.resource.remote import NetworkSiSPMPowerPort
from labgrid.driver.powerdriver import SiSPMPowerDriver


def test_sispm_create(target):
    r = NetworkSiSPMPowerPort(target,
            name=None,
            host="localhost",
            busnum=0,
            devnum=1,
            path='0:1',
            vendor_id=0x0,
            model_id=0x0,
            index=1,
    )
    d = SiSPMPowerDriver(target, name=None)
    assert (isinstance(d, SiSPMPowerDriver))
