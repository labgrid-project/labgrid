from unittest.mock import MagicMock
import pytest
from labgrid import Target
from labgrid.resource import SerialPort
from labgrid.driver import SerialDriver

@pytest.fixture(scope='function')
def target():
    t = Target('Test')
    return t

@pytest.fixture(scope='function')
def port(target, monkeypatch):
    serial_mock = MagicMock
    import serial
    monkeypatch.setattr(serial, 'Serial', serial_mock)
    s = SerialPort(target,'port')
    return s
