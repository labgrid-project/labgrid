import attr
import pytest
from unittest.mock import MagicMock
from labgrid import target_factory, Target
from labgrid.resource import SerialPort
from labgrid.driver import SerialDriver
from labgrid.protocol import ConsoleProtocol


@pytest.fixture(scope='function')
def target():
    return Target('Test')


@pytest.fixture(scope='function')
def serial_port(target):
    target.add_resource(SerialPort('/dev/test'))
    return target


@pytest.fixture(scope='function')
def serial_driver(serial_port, monkeypatch):
    serial_mock = MagicMock
    import serial
    monkeypatch.setattr(serial, 'Serial', serial_mock)
    s = SerialDriver(serial_port)
    return serial_port


@target_factory.reg_driver
@attr.s
class FakeConsoleDriver(ConsoleProtocol):
    target = attr.ib()

    def __attrs_post_init__(self):
        self.target.drivers.append(self)

    def read(self, *args):
        pass

    def write(self, *args):
        pass

    def open(self):
        pass

    def close(self):
        pass
