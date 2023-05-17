import logging
from pathlib import Path
from signal import SIGTERM
import sys
import threading

import pytest
import pexpect
import yaml

from labgrid import Target
from labgrid.driver import SerialDriver
from labgrid.resource import RawSerialPort, NetworkSerialPort
from labgrid.driver.fake import FakeConsoleDriver

@pytest.fixture(scope="session")
def curses_init():
    """ curses only reads the terminfo DB once on the first import, so make
    sure we prime it correctly."""
    try:
        import curses
        curses.setupterm("linux")
    except ModuleNotFoundError:
        logging.warning("curses module not found, not setting up a default terminal – tests may fail")

def keep_reading(spawn):
    "The output from background processes must be read to avoid blocking them."
    while spawn.isalive():
        try:
            data = spawn.read_nonblocking(size=1024, timeout=0.1)
            if not data:
                return
        except pexpect.TIMEOUT:
            continue
        except pexpect.EOF:
            return
        except OSError:
            return


class Prefixer:
    def __init__(self, wrapped, prefix):
        self.__wrapped = wrapped
        self.__prefix = prefix.encode()+b": "
        self.__continuation = False

    def write(self, data):
        if data[-1:] == b'\n':
            continuation = False
            data = data[:-1]
        else:
            continuation = True
        data = data.replace(b'\n', b'\n'+self.__prefix)
        if not self.__continuation:
            data = self.__prefix+data
        if not continuation:
            data += b'\n'
        self.__continuation = continuation
        self.__wrapped.write(data)

    def __getattr__(self, name):
        return getattr(self.__wrapped, name)


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
def crossbar_config(tmpdir, pytestconfig):
    crossbar_config = '.crossbar/config-anonymous.yaml'

    pytestconfig.rootdir.join(crossbar_config).copy(tmpdir.mkdir('.crossbar'))
    crossbar_config = tmpdir.join(crossbar_config)

    # crossbar runs labgrid's coordinator component as a guest, record its coverage
    if pytestconfig.pluginmanager.get_plugin('pytest_cov'):
        with open(crossbar_config, 'r+') as stream:
            conf = yaml.safe_load(stream)

            for worker in conf['workers']:
                if worker['type'] == 'guest':
                    worker['executable'] = 'coverage'
                    worker['arguments'].insert(0, 'run')
                    worker['arguments'].insert(1, '--parallel-mode')
                    # pytest-cov combines coverage files in root dir automatically, so copy it there
                    coverage_data = pytestconfig.rootdir.join('.coverage')
                    worker['arguments'].insert(2, f'--data-file={coverage_data}')

            stream.seek(0)
            yaml.safe_dump(conf, stream)

    return crossbar_config

@pytest.fixture(scope='function')
def crossbar(tmpdir, pytestconfig, crossbar_config):
    crossbar_venv = Path(pytestconfig.getoption("--crossbar-venv"))
    if not crossbar_venv.is_absolute():
        crossbar_venv = pytestconfig.rootdir / crossbar_venv
    crossbar_bin = crossbar_venv / "bin/crossbar"

    spawn = pexpect.spawn(
        f'{crossbar_bin} start --color false --logformat none --config {crossbar_config}',
        logfile=Prefixer(sys.stdout.buffer, 'crossbar'),
        cwd=str(tmpdir))
    try:
        spawn.expect('Realm .* started')
        spawn.expect('Guest .* started')
        spawn.expect('Coordinator ready')
    except:
        print(f"crossbar startup failed with {spawn.before}")
        raise
    reader = threading.Thread(target=keep_reading, name='crossbar-reader', args=(spawn,), daemon=True)
    reader.start()
    yield spawn

    # let coverage write its data:
    # https://coverage.readthedocs.io/en/latest/subprocess.html#process-termination
    print("stopping crossbar")
    spawn.kill(SIGTERM)
    spawn.expect(pexpect.EOF)
    spawn.wait()

    reader.join()

@pytest.fixture(scope='function')
def exporter(tmpdir, crossbar):
    p = tmpdir.join("exports.yaml")
    p.write(
        """
    Testport:
        NetworkSerialPort:
          host: 'localhost'
          port: 4000
    Broken:
        RawSerialPort:
          port: 'none'
    Many:
        NetworkSerialPort:
          host: 'localhost'
          port: 4000
        NetworkService:
          address: "192.168.0.1"
          username: "root"
    """
    )
    spawn = pexpect.spawn(
            f'{sys.executable} -m labgrid.remote.exporter --name testhost exports.yaml',
            logfile=Prefixer(sys.stdout.buffer, 'exporter'),
            cwd=str(tmpdir))
    try:
        spawn.expect('exporter/testhost')
    except:
        print(f"exporter startup failed with {spawn.before}")
        raise
    reader = threading.Thread(target=keep_reading, name='exporter-reader', args=(spawn,), daemon=True)
    reader.start()
    yield spawn
    print("stopping exporter")
    spawn.close(force=True)
    assert not spawn.isalive()
    reader.join()

def pytest_addoption(parser):
    parser.addoption("--sigrok-usb", action="store_true",
                     help="Run sigrok usb tests with fx2lafw device (0925:3881)")
    parser.addoption("--local-sshmanager", action="store_true",
                     help="Run SSHManager tests against localhost")
    parser.addoption("--ssh-username", default=None,
                     help="SSH username to use for SSHDriver testing")
    parser.addoption("--crossbar-venv", default=None,
                     help="Path to separate virtualenv with crossbar installed")

def pytest_configure(config):
    # register an additional marker
    config.addinivalue_line("markers",
                            "sigrokusb: enable fx2lafw USB tests (0925:3881)")
    config.addinivalue_line("markers",
                            "localsshmanager: test SSHManager against Localhost")
    config.addinivalue_line("markers",
                            "sshusername: test SSHDriver against Localhost")
    config.addinivalue_line("markers",
                            "crossbar: test against local crossbar")

def pytest_runtest_setup(item):
    envmarker = item.get_closest_marker("sigrokusb")
    if envmarker is not None:
        if item.config.getoption("--sigrok-usb") is False:
            pytest.skip("sigrok usb tests not enabled (enable with --sigrok-usb)")
    envmarker = item.get_closest_marker("localsshmanager")
    if envmarker is not None:
        if item.config.getoption("--local-sshmanager") is False:
            pytest.skip("SSHManager tests against localhost not enabled (enable with --local-sshmanager)")
    envmarker = item.get_closest_marker("sshusername")
    if envmarker is not None:
        if item.config.getoption("--ssh-username") is None:
            pytest.skip("SSHDriver tests against localhost not enabled (enable with --ssh-username <username>)")
    envmarker = item.get_closest_marker("crossbar")
    if envmarker is not None:
        if item.config.getoption("--crossbar-venv") is None:
            pytest.skip("No path to crossbar virtualenv given (set with --crossbar-venv <path>)")
