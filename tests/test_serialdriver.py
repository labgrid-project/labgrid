import pytest

from labgrid.driver import SerialDriver
from labgrid.exceptions import NoSupplierFoundError


class TestSerialDriver:
    def test_instanziation_fail_missing_port(self, target):
        with pytest.raises(NoSupplierFoundError):
            SerialDriver(target, "serial")

    def test_instanziation(self, target, serial_port, mocker):
        serial_mock = mocker.patch('serial.Serial')
        s = SerialDriver(target, "serial")
        assert (isinstance(s, SerialDriver))
        assert (target.drivers[0] == s)

    def test_write(self, target, serial_port, mocker):
        serial_mock = mocker.patch('serial.Serial')
        s = SerialDriver(target, "serial")
        target.activate(s)
        s.write(b"testdata")
        serial_mock.return_value.open.assert_called_once_with()
        serial_mock.return_value.write.assert_called_once_with(b"testdata")

    def test_read(self, target, serial_port, mocker):
        serial_mock = mocker.patch('serial.Serial')
        serial_mock.return_value.in_waiting = 0
        s = SerialDriver(target, "serial")
        target.activate(s)
        s.read()
        serial_mock.return_value.open.assert_called_once_with()
        serial_mock.return_value.read.assert_called_once_with(1)

    def test_close(self, target, serial_port, mocker):
        serial_mock = mocker.patch('serial.Serial')
        s = SerialDriver(target, "serial")
        target.activate(s)
        s.close()
        serial_mock.return_value.open.assert_called_once_with()
        serial_mock.return_value.close.assert_called_once_with()

    def test_deactivate(self, target, serial_port, mocker):
        serial_mock = mocker.patch('serial.Serial')
        s = SerialDriver(target, "serial")
        target.activate(s)
        target.deactivate(s)
        serial_mock.return_value.open.assert_called_once_with()
        serial_mock.return_value.close.assert_called_once_with()

    def test_rfc2711_instanziation(self, target, serial_rfc2711_port, mocker):
        serial_mock = mocker.patch('serial.rfc2217.Serial')
        s = SerialDriver(target, "serial")
        assert (isinstance(s, SerialDriver))
        assert (target.drivers[0] == s)
        serial_mock.assert_called_once_with()

    def test_raw_instanziation(self, target, serial_raw_port, mocker):
        serial_mock = mocker.patch('serial.serial_for_url')
        s = SerialDriver(target, "serial")
        assert (isinstance(s, SerialDriver))
        assert (target.drivers[0] == s)
        serial_mock.assert_called_once_with('socket://', do_not_open=True)
