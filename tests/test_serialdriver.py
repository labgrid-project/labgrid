import pytest

from labgrid.driver import SerialDriver

class TestSerialDriver:
    def test_instanziation_fail_missing_port(self, target):
        with pytest.raises(NotImplementedError):
            SerialDriver(target)

    def test_instanziation(self, target, port):
        SerialDriver(target)


























