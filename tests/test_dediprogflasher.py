import pytest

from labgrid.resource.dediprogflasher import DediprogFlasher, NetworkDediprogFlasher
from labgrid.driver.dediprogflashdriver import DediprogFlashDriver


def test_dediprog_network_create(target):
    r = NetworkDediprogFlasher(target, name=None, vcc='3.5V', host='localhost')
    assert isinstance(r, NetworkDediprogFlasher)
    d = DediprogFlashDriver(target, name=None)
    assert isinstance(d, DediprogFlashDriver)


def test_dediprog_driver_create(target):
    r = DediprogFlasher(target, name=None, vcc='2.5V')
    assert isinstance(r, DediprogFlasher)

    d = DediprogFlashDriver(target, name=None)
    assert isinstance(d, DediprogFlashDriver)

def test_dediprog_driver_map_vcc(target):
    r = DediprogFlasher(target, name=None, vcc='2.5V')
    d = DediprogFlashDriver(target, name=None)

    m = d.map_vcc()
    assert isinstance(m, str)
    assert m == '1'

def test_dediprog_driver_map_vcc_inv(target):
    with pytest.raises(ValueError):
        r = DediprogFlasher(target, name=None, vcc='2.6V')
