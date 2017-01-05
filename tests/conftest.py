from unittest.mock import MagicMock

import attr
import pytest

from labgrid import Target, target_factory
from labgrid.driver import SerialDriver
from labgrid.protocol import CommandProtocol, ConsoleProtocol
from labgrid.resource import SerialPort


@pytest.fixture(scope='function')
def target():
    return Target('Test')


@pytest.fixture(scope='function')
def serial_port(target):
    return SerialPort(target, '/dev/test')


@pytest.fixture(scope='function')
def serial_driver(target, serial_port, monkeypatch):
    serial_mock = MagicMock
    import serial
    monkeypatch.setattr(serial, 'Serial', serial_mock)
    s = SerialDriver(target)
    return s
