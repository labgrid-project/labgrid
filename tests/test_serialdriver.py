from unittest.mock import MagicMock
import pytest
import serial

from labgrid.driver import SerialDriver, NoResourceException

class TestSerialDriver:
    def test_instanziation_fail_missing_port(self, target):
        with pytest.raises(NoResourceException):
            SerialDriver(target)

    def test_instanziation(self, serial_port, monkeypatch):
        serial_mock = MagicMock
        monkeypatch.setattr(serial, 'Serial', serial_mock)
        s = SerialDriver(serial_port)
        assert(isinstance(s, SerialDriver))
        assert(serial_port.drivers[0] == s)
