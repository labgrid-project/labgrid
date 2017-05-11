from importlib.util import find_spec

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
def serial_driver(target, serial_port, monkeypatch, mocker):
    serial_mock = mocker.MagicMock
    import serial
    monkeypatch.setattr(serial, 'Serial', serial_mock)
    s = SerialDriver(target)
    return s

@pytest.fixture(scope='function')
def crossbar(tmpdir):
    if not find_spec('crossbar'):
        pytest.skip("crossbar not found")
    local(__name__).dirpath('.crossbar/config.yaml').copy(tmpdir.mkdir('.crossbar'))
    spawn = pexpect.spawn('crossbar start --logformat none', cwd=str(tmpdir))
    try:
        spawn.expect('Realm .* started')
        spawn.expect('Guest .* started')
        spawn.expect('Coordinator ready')
    except:
        print("crossbar startup failed with {}".format(spawn.before))
        raise
    yield spawn
    spawn.close(force=True)
    assert not spawn.isalive()
