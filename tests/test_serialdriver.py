import pytest
import serial

from labgrid.driver import SerialDriver
from labgrid.exceptions import NoSupplierFoundError


class TestSerialDriver:
    def test_instanziation_fail_missing_port(self, target):
        with pytest.raises(NoSupplierFoundError):
            SerialDriver(target)

    def test_instanziation(self, target, serial_port, monkeypatch, mocker):
        serial_mock = mocker.Mock()
        monkeypatch.setattr(serial, 'Serial', serial_mock)
        s = SerialDriver(target)
        assert (isinstance(s, SerialDriver))
        assert (target.drivers[0] == s)

    def test_write(self, target, monkeypatch, serial_port, mocker):
        serial_mock = mocker.Mock()
        serial_mock.write = mocker.MagicMock()
        monkeypatch.setattr(serial, 'Serial', serial_mock)
        s = SerialDriver(target)
        s.serial = serial_mock
        target.activate(s)
        s.write(b"testdata")
        serial_mock.write.assert_called_with(b"testdata")

    def test_read(self, target, monkeypatch, serial_port, mocker):
        serial_mock = mocker.Mock()
        serial_mock.read = mocker.MagicMock()
        serial_mock.in_waiting = 0
        monkeypatch.setattr(serial, 'Serial', serial_mock)
        s = SerialDriver(target)
        s.serial = serial_mock
        target.activate(s)
        s.read()
        assert (serial_mock.read.called)

    def test_close(self, target, monkeypatch, serial_port, mocker):
        serial_mock = mocker.Mock()
        serial_mock.close = mocker.MagicMock()
        monkeypatch.setattr(serial, 'Serial', serial_mock)
        s = SerialDriver(target)
        s.serial = serial_mock
        target.activate(s)
        s.close()
        assert (serial_mock.close.called)
