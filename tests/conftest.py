from unittest.mock import MagicMock

import attr
import pytest
import pexpect
from py.path import local

from labgrid import Target, target_factory
from labgrid.driver import SerialDriver
from labgrid.protocol import CommandProtocol, ConsoleProtocol
from labgrid.resource import RawSerialPort


@pytest.fixture(scope='function')
def target():
    return Target('Test')


@pytest.fixture(scope='function')
def serial_port(target):
    return RawSerialPort(target, '/dev/test')


@pytest.fixture(scope='function')
def serial_driver(target, serial_port, monkeypatch):
    serial_mock = MagicMock
    import serial
    monkeypatch.setattr(serial, 'Serial', serial_mock)
    s = SerialDriver(target)
    return s


@pytest.fixture(scope='function')
def crossbar(tmpdir):
    pytest.importorskip('crossbar')
    local(__name__).dirpath('.crossbar/config.yaml').copy(tmpdir.mkdir('.crossbar'))
    spawn = pexpect.spawn('crossbar start --logformat none', cwd=str(tmpdir))
    spawn.expect('Realm .* started')
    spawn.expect('Guest .* started')
    spawn.expect('Coordinator ready')
    yield spawn
    with pexpect.spawn('crossbar stop', cwd=str(tmpdir)) as stop_spawn:
        stop_spawn.expect(pexpect.EOF)
    assert stop_spawn.exitstatus == 0
    spawn.expect(pexpect.EOF)
    assert spawn.exitstatus == 0
