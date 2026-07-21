import logging
import os
from signal import SIGTERM
import sys
import threading
import time

import pytest
import pexpect

from labgrid import Target
from labgrid.driver import SerialDriver
from labgrid.resource import RawSerialPort, NetworkSerialPort
from labgrid.driver.fake import FakeConsoleDriver

psutil = pytest.importorskip("psutil")

# gRPC is only safe to fork() if gRPC objects are created in the child after the fork. The tests do
# the opposite: the pytest process spawns labgrid-client via pexpect (forkpty) while gRPC is
# already initialized in it, so gRPC's pthread_atfork handler can lose a race and abort the child
# before it execs. Set GRPC_ENABLE_FORK_SUPPORT=0 to disable the handler; the spawned clients
# fork+exec and never reuse an inherited channel, so it is not needed anyway.
# See also https://github.com/grpc/grpc/blob/master/doc/fork_support.md
os.environ.setdefault("GRPC_ENABLE_FORK_SUPPORT", "0")


@pytest.fixture(scope="session")
def curses_init():
    """ curses only reads the terminfo DB once on the first import, so make
    sure we prime it correctly."""
    try:
        import curses
        curses.setupterm("linux")
    except ModuleNotFoundError:
        logging.warning("curses module not found, not setting up a default terminal – tests may fail")


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


class _LockedSpawn:
    """
    pexpect/ptyprocess is not thread-safe.
    Serialize access to pexpect.spawn through a lock, so the reader thread and the main thread
    never call into pexpect (and thus os.waitpid()) concurrently.
    """

    def __init__(self, spawn):
        self._spawn = spawn
        self._lock = threading.Lock()

    def __getattr__(self, name):
        with self._lock:
            attr = getattr(self._spawn, name)
        if callable(attr):
            def locked(*args, **kwargs):
                with self._lock:
                    return attr(*args, **kwargs)
            return locked
        return attr


class LabgridComponent:
    def __init__(self, cwd):
        self.cwd = str(cwd)
        self.spawn = None
        self.reader = None

    @property
    def spawn(self):
        return self._spawn

    @spawn.setter
    def spawn(self, spawn):
        self._spawn = _LockedSpawn(spawn) if spawn is not None else None

    def stop(self):
        logging.info("stopping %s pid=%s", self.__class__.__name__, self.spawn.pid)

        # let coverage write its data:
        # https://coverage.readthedocs.io/en/latest/subprocess.html#process-termination
        self.spawn.kill(SIGTERM)
        if not self.spawn.closed:
            self.spawn.expect(pexpect.EOF)
            self.spawn.wait()
        assert not self.spawn.isalive()

        self.spawn = None
        self.stop_reader()

    @staticmethod
    def keep_reading(spawn):
        "The output from background processes must be read to avoid blocking them."
        while spawn.isalive():
            try:
                data = spawn.read_nonblocking(size=1024, timeout=0)
                if not data:
                    return
            except pexpect.TIMEOUT:
                pass
            except pexpect.EOF:
                return
            except OSError:
                return

            # give external LabgridComponent.spawn users a chance to acquire the lock
            time.sleep(0.001)

    def start_reader(self):
        self.reader = threading.Thread(
            target=LabgridComponent.keep_reading,
            name=f'{self.__class__.__name__}-reader-{self.pid}',
            args=(self.spawn,), daemon=True)
        self.reader.start()

    def stop_reader(self):
        self.reader.join()

        self.reader = None

    def isalive(self):
        return self.spawn.isalive()

    @property
    def exitstatus(self):
        return self.spawn.exitstatus

    @property
    def pid(self):
        return self.spawn.pid

    def suspend_tree(self):
        main = psutil.Process(self.pid)
        main.suspend()
        for child in main.children(recursive=True):
            child.suspend()

    def resume_tree(self):
        main = psutil.Process(self.pid)
        main.resume()
        for child in main.children(recursive=True):
            child.resume()


class Exporter(LabgridComponent):
    def __init__(self, config, cwd):
        super().__init__(cwd)
        self.config = config

    def start(self):
        assert self.spawn is None
        assert self.reader is None

        self.spawn = pexpect.spawn(
            f'python -m labgrid.remote.exporter --name testhost {self.config}',
            logfile=Prefixer(sys.stdout.buffer, 'exporter'),
            cwd=self.cwd)
        try:
            self.spawn.expect('exporter name: testhost')
            self.spawn.expect('connected to coordinator')
        except Exception as e:
            raise Exception(f"exporter startup failed with {self.spawn.before}") from e

        self.start_reader()


class Coordinator(LabgridComponent):
    def start(self, args=''):
        assert self.spawn is None
        assert self.reader is None

        cmd = 'python -m labgrid.remote.coordinator'
        if args:
            cmd = f'{cmd} {args}'
        self.spawn = pexpect.spawn(
            cmd,
            logfile=Prefixer(sys.stdout.buffer, 'coordinator'),
            cwd=self.cwd)
        try:
            self.spawn.expect('Coordinator ready')
        except Exception as e:
            raise Exception(f"coordinator startup failed with {self.spawn.before}") from e

        self.start_reader()


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
def coordinator(tmpdir):
    coordinator = Coordinator(tmpdir)
    coordinator.start()

    yield coordinator

    coordinator.stop()

@pytest.fixture(scope='function')
def coordinator_with_env(tmpdir):
    env_file = tmpdir.join('env.yaml')
    env_file.write('targets:\n')
    coordinator = Coordinator(tmpdir)
    coordinator.start(f'--environment {env_file}')

    yield coordinator, env_file

    coordinator.stop()

@pytest.fixture(scope='function')
def exporter(tmpdir, coordinator):
    config = "exports.yaml"
    p = tmpdir.join(config)
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

    exporter = Exporter(config, tmpdir)
    exporter.start()

    yield exporter

    exporter.stop()

def pytest_addoption(parser):
    parser.addoption("--sigrok-usb", action="store_true",
                     help="Run sigrok usb tests with fx2lafw device (0925:3881)")
    parser.addoption("--local-sshmanager", action="store_true",
                     help="Run SSHManager tests against localhost")
    parser.addoption("--ssh-username", default=None,
                     help="SSH username to use for SSHDriver testing")

def pytest_configure(config):
    # register an additional marker
    config.addinivalue_line("markers",
                            "sigrokusb: enable fx2lafw USB tests (0925:3881)")
    config.addinivalue_line("markers",
                            "localsshmanager: test SSHManager against Localhost")
    config.addinivalue_line("markers",
                            "sshusername: test SSHDriver against Localhost")
    config.addinivalue_line("markers",
                            "coordinator: test against local coordinator")

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
