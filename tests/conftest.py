from importlib.util import find_spec

import pytest
import pexpect

from labgrid import Target
from labgrid.driver import SerialDriver
from labgrid.resource import RawSerialPort, NetworkSerialPort
from labgrid.driver.fake import FakeConsoleDriver


@pytest.fixture(scope='function')
def target():
    return Target('Test')

@pytest.fixture(scope='function')
def target_with_fakeconsole():
    t = Target('dummy')
    cp = FakeConsoleDriver(t, "console")
    return t

@pytest.fixture(scope='function')
def serial_port(target):
    return RawSerialPort(target, 'serial', '/dev/test')

@pytest.fixture(scope='function')
def serial_rfc2711_port(target):
    return NetworkSerialPort(target, 'rfc2711', host='localhost', port=8888)

@pytest.fixture(scope='function')
def serial_raw_port(target):
    return NetworkSerialPort(target, 'serialraw', host='localhost', port=8888, protocol="raw")


@pytest.fixture(scope='function')
def serial_driver(target, serial_port, mocker):
    m = mocker.patch('serial.Serial')
    s = SerialDriver(target, 'serial')
    target.activate(s)
    return s

@pytest.fixture(scope='function')
def serial_driver_no_name(target, serial_port, mocker):
    m = mocker.patch('serial.Serial')
    s = SerialDriver(target, None)
    target.activate(s)
    return s

@pytest.fixture(scope='function')
def crossbar(tmpdir, pytestconfig):
    if not find_spec('crossbar'):
        pytest.skip("crossbar not found")
    pytestconfig.rootdir.join('.crossbar/config.yaml').copy(tmpdir.mkdir('.crossbar'))
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

@pytest.fixture(scope='function')
def exporter(tmpdir):
    p = tmpdir.join("exports.yaml")
    p.write(
        """
    Testport:
        NetworkSerialPort:
          {host: 'localhost', port: 4000}
    """
    )
    spawn = pexpect.spawn('labgrid-exporter exports.yaml', cwd=str(tmpdir))
    try:
        spawn.expect('SessionDetails')
    except:
        print("exporter startup failed with {}".format(spawn.before))
        raise
    yield spawn
    spawn.close(force=True)
    assert not spawn.isalive()

def pytest_addoption(parser):
    parser.addoption("--sigrok-usb", action="store_true",
                     help="Run sigrok usb tests with fx2lafw device (0925:3881)")
    parser.addoption("--local-sshmanager", action="store_true",
                     help="Run SSHManager tests against localhost")

def pytest_configure(config):
    # register an additional marker
    config.addinivalue_line("markers",
                            "sigrokusb: enable fx2lafw USB tests (0925:3881)")
    config.addinivalue_line("markers",
                            "localsshmanager: test SSHManager against Localhost")

def pytest_runtest_setup(item):
    envmarker = item.get_closest_marker("sigrokusb")
    if envmarker is not None:
        if item.config.getoption("--sigrok-usb") is False:
            pytest.skip("sigrok usb tests not enabled (enable with --sigrok-usb)")
    envmarker = item.get_marker("localsshmanager")
    if envmarker is not None:
        if item.config.getoption("--local-sshmanager") is False:
            pytest.skip("SSHManager tests against localhost not enabled (enable with --local-sshmanager)")
