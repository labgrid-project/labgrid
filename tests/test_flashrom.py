from labgrid.resource.flashrom import Flashrom, NetworkFlashrom
from labgrid.driver.flashromdriver import FlashromDriver


def test_flashrom_network_create(target):
    r = NetworkFlashrom(target,
                       name=None,
                       programmer='linux_spi:dev=/dev/spidev0.1,spispeed=30000',
                       host='localhost')
    assert (isinstance(r, NetworkFlashrom))
    d = FlashromDriver(target, name=None)
    assert (isinstance(d, FlashromDriver))


def test_flashrom_driver_create(target):
    r = Flashrom(target,
                 name=None,
                 programmer='linux_spi:dev=/dev/spidev0.1,spispeed=30000')
    assert (isinstance(r, Flashrom))

    d = FlashromDriver(target, name=None)
    assert (isinstance(d, FlashromDriver))
