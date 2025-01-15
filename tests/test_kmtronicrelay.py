from labgrid.resource.udev import KMTronicRelay
from labgrid.driver.kmtronicrelay import KMTronicRelayDriver


def test_kmtronicrelay_resource(target):
    r = KMTronicRelay(target, name=None, match={"ID_SERIAL_SHORT": "AB0LBF2U"})


def test_kmtronicrelay_driver(target):
    r = KMTronicRelay(target, name=None, match={"ID_SERIAL_SHORT": "AB0LBF2U"})
    d = KMTronicRelayDriver(target, name=None)
    target.activate(d)


def test_kmtronicrelay_control(target):
    r = KMTronicRelay(target, name=None, match={"ID_SERIAL_SHORT": "AB0LBF2U"})
    d = KMTronicRelayDriver(target, name=None)
    target.activate(d)
    d.set(1)
    assert d.get() == 1
    d.set(0)
    assert d.get() == 0
