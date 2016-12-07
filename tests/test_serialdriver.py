import pytest

from labgrid.driver import SerialDriver, NoResourceException

class TestSerialDriver:
    def test_instanziation_fail_missing_port(self, target):
        with pytest.raises(NoResourceException):
            SerialDriver(target)

    def test_instanziation(self, target, port):
        SerialDriver(target)


























