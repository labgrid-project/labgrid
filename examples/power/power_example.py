import pytest


@pytest.fixture()
def pdu(target):
    return target.get_driver("NetworkPowerDriver")


def test_something(pdu):
    pdu.on()
    # Note that the pdu might not have switched on when requesting it's
    # status immediately
    assert pdu.get() is True

    # ... do something

    pdu.off()
    assert pdu.get() is False
