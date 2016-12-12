from unittest.mock import MagicMock
import pytest
from labgrid import Target
from labgrid.resource import SerialPort
from labgrid.driver import SerialDriver

@pytest.fixture(scope='function')
def target():
    return Target('Test')

@pytest.fixture(scope='function')
def serial_port(target):
    SerialPort(target,'/dev/test')
    return target

@pytest.fixture(scope='function')
def serial_driver(serial_port, monkeypatch):
    serial_mock = MagicMock
    import serial
    monkeypatch.setattr(serial, 'Serial', serial_mock)
    s = SerialDriver(serial_port,'port')
    return serial_port
