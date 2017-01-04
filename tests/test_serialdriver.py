from unittest.mock import MagicMock, Mock

import pytest
import serial

from labgrid.driver import NoResourceError, SerialDriver


class TestSerialDriver:
    def test_instanziation_fail_missing_port(self, target):
        with pytest.raises(NoResourceError):
            SerialDriver(target)

    def test_instanziation(self, serial_port, monkeypatch):
        serial_mock = Mock()
        monkeypatch.setattr(serial, 'Serial', serial_mock)
        s = SerialDriver(serial_port)
        assert (isinstance(s, SerialDriver))
        assert (serial_port.drivers[0] == s)

    def test_write(self, monkeypatch, serial_port):
        serial_mock = Mock()
        serial_mock.write = MagicMock()
        monkeypatch.setattr(serial, 'Serial', serial_mock)
        s = SerialDriver(serial_port)
        s.serial = serial_mock
        s.write(b"testdata")
        serial_mock.write.assert_called_with(b"testdata")

    def test_read(self, monkeypatch, serial_port):
        serial_mock = Mock()
        serial_mock.read = MagicMock()
        monkeypatch.setattr(serial, 'Serial', serial_mock)
        s = SerialDriver(serial_port)
        s.serial = serial_mock
        s.read()
        assert (serial_mock.read.called)

    def test_close(self, monkeypatch, serial_port):
        serial_mock = Mock()
        serial_mock.close = MagicMock()
        monkeypatch.setattr(serial, 'Serial', serial_mock)
        s = SerialDriver(serial_port)
        s.serial = serial_mock
        s.close()
        assert (serial_mock.close.called)
