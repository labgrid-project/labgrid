from unittest.mock import MagicMock
import serial
from labgrid.resource import SerialPort # pylint: disable=import-error
from labgrid import Target # pylint: disable=import-error

class TestSerialPort:
    def test_instanziation(self, monkeypatch):
        t = Target("Test")
        serial_mock = MagicMock
        monkeypatch.setattr(serial, 'Serial', serial_mock)
        s = SerialPort(t,'port')
        assert(isinstance(s, SerialPort))
        assert(t.resources[0] == s)
