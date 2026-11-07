import json
import socket
import subprocess
import threading
import time

import pytest

from labgrid.driver import QEMUDriver
from labgrid.driver.exception import ExecutionError
from labgrid import Environment

@pytest.fixture
def qemu_env(tmpdir):
    p = tmpdir.join("config.yaml")
    p.write(
        """
        targets:
          main:
            role: foo
        images:
          kernel: "test.zImage"
          dtb: test.dtb"
        tools:
          qemu: "qemu-system-arm"
        paths:
          rootfs: "test/path"
        """
    )
    return Environment(str(p))

@pytest.fixture
def qemu_target(qemu_env):
    return qemu_env.get_target()

@pytest.fixture
def qemu_driver(qemu_target, qemu_mock):
    q = QEMUDriver(
        qemu_target,
        "qemu",
        qemu_bin="qemu",
        machine='',
        cpu='',
        memory='',
        boot_args='',
        extra_args='',
        kernel='kernel',
        rootfs='rootfs')
    return q

@pytest.fixture
def qemu_mock(mocker):
    popen_mock = mocker.patch('subprocess.Popen')
    instance_mock = mocker.MagicMock()
    instance_mock.stdout.readline.return_value = b"""
    {
      "QMP": {
        "version": {}
      },
      "return": {}
    }
    """

    instance_mock.wait = mocker.MagicMock(side_effect=subprocess.TimeoutExpired(cmd='qemu', timeout=0.5))
    instance_mock.communicate = mocker.MagicMock(return_value=(b"", b""))
    popen_mock.return_value = instance_mock

    select_mock = mocker.patch('select.select')
    select_mock.return_value = True, None, None

    socket_mock = mocker.patch('socket.socket')
    socket_mock.return_value.accept.return_value = mocker.MagicMock(), ''

    version_mock = mocker.patch('subprocess.run')
    version_mock.return_value.returncode = 0
    version_mock.return_value.stdout = "QEMU emulator version 4.2.1"

@pytest.fixture
def qemu_qmp_mock(mocker):
    monitor_mock = mocker.patch('labgrid.driver.qemudriver.QMPMonitor')
    monitor_mock.return_value.execute.return_value = {'return': {}}
    return monitor_mock

def test_qemu_instance(qemu_driver):
    assert (isinstance(qemu_driver, QEMUDriver))

def test_qemu_base_args_optional(qemu_target, qemu_mock):
    q = QEMUDriver(
        qemu_target,
        "qemu_opt",
        qemu_bin="qemu",
        machine="pc",
        cpu="cortex-a15",
        memory="512M",
        extra_args="-d guest_errors",
        kernel="kernel",
        rootfs="rootfs")
    args = q.get_qemu_base_args()

    assert args[args.index("-machine") + 1] == "pc"
    assert args[args.index("-cpu") + 1] == "cortex-a15"
    assert args[args.index("-d") + 1] == "guest_errors"

def test_qemu_base_args_defaults(qemu_target, qemu_mock):
    q = QEMUDriver(
        qemu_target,
        "qemu_default",
        qemu_bin="qemu",
        memory="512M",
        kernel="kernel",
        rootfs="rootfs")
    args = q.get_qemu_base_args()

    assert "-machine" not in args
    assert "-cpu" not in args

def test_qemu_extra_args_append_rejected(qemu_target, qemu_mock):
    q = QEMUDriver(
        qemu_target,
        "qemu_append",
        qemu_bin="qemu",
        memory="512M",
        extra_args="-append root=/dev/foo",
        kernel="kernel",
        rootfs="rootfs")
    with pytest.raises(ExecutionError):
        q.get_qemu_base_args()

def test_qemu_activate_deactivate(qemu_target, qemu_driver, qemu_qmp_mock):
    qemu_target.activate(qemu_driver)

    qemu_driver.monitor_command("info")
    qemu_qmp_mock.assert_called_once()
    qemu_qmp_mock.return_value.execute.assert_called_with("info", {})

    qemu_target.deactivate(qemu_driver)

def test_qemu_on_off(qemu_target, qemu_driver):
    qemu_target.activate(qemu_driver)

    qemu_driver.on()
    qemu_driver.off()

    qemu_target.deactivate(qemu_driver)

def test_qemu_read_write(qemu_target, qemu_driver):
    qemu_target.activate(qemu_driver)

    qemu_driver.on()
    qemu_driver.read()
    qemu_driver.read(max_size=10)
    qemu_driver.write(b'abc')

    qemu_target.deactivate(qemu_driver)

def test_qemu_port_forwarding(qemu_target, qemu_driver, qemu_mock):
    qemu_target.activate(qemu_driver)

    qemu_driver.on()
    qemu_driver.add_port_forward('tcp', '127.0.0.1', 8080, '127.0.0.1', 80)
    assert ('tcp', '127.0.0.1', 8080, '') in qemu_driver._forwarded_ports.keys()
    qemu_driver.remove_port_forward('tcp', '127.0.0.1', 8080)
    assert qemu_driver._forwarded_ports == {}

    qemu_target.deactivate(qemu_driver)

def test_qemu_port_forwarding_with_netdev(qemu_target, qemu_driver, qemu_mock):
    qemu_target.activate(qemu_driver)

    qemu_driver.on()
    qemu_driver.add_port_forward('tcp', '127.0.0.1', 8080, '127.0.0.1', 80, netdev='netdev0')
    assert ('tcp', '127.0.0.1', 8080, 'netdev0') in qemu_driver._forwarded_ports.keys()
    qemu_driver.remove_port_forward('tcp', '127.0.0.1', 8080, netdev='netdev0')
    assert qemu_driver._forwarded_ports == {}

    qemu_target.deactivate(qemu_driver)

def test_qemu_qmp_uses_stdio_by_default(qemu_target, qemu_driver):
    qemu_target.activate(qemu_driver)

    cmd = subprocess.Popen.call_args.args[0]
    assert cmd[cmd.index("-qmp") + 1] == "stdio"

    qemu_target.deactivate(qemu_driver)

def test_qemu_qmp_socket_replaces_stdio(qemu_target, qemu_mock, qemu_qmp_mock):
    driver = QEMUDriver(
        qemu_target,
        "qemu",
        qemu_bin="qemu",
        machine='',
        cpu='',
        memory='',
        kernel='kernel',
        rootfs='rootfs',
        qmp_socket=True)
    qemu_target.activate(driver)

    cmd = subprocess.Popen.call_args.args[0]
    assert "stdio" not in cmd
    assert f"unix:{driver._tempdir}/qmp,server,nowait" in cmd

    qemu_target.deactivate(driver)

class FakeQEMU:
    """Answers QMP commands on a unix socket, like QEMU with -qmp unix:..."""
    def __init__(self, cmd, qmp_delay):
        self.qmp_path = cmd[cmd.index("-qmp") + 1].split(":", 1)[1].split(",")[0]
        self.serial_path = cmd[cmd.index("-chardev") + 1].split("path=", 1)[1]
        self.qmp_delay = qmp_delay
        self.commands = []
        self.qmp_closed = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        serial = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        serial.connect(self.serial_path)
        time.sleep(self.qmp_delay)
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(self.qmp_path)
        server.listen(1)
        conn, _ = server.accept()
        self._serve_qmp(conn)
        conn.close()
        server.close()
        serial.close()

    def _serve_qmp(self, conn):
        conn.sendall(b'{"QMP": {"version": {}}}\n')
        for line in conn.makefile("rb"):
            self.commands.append(json.loads(line)["execute"])
            conn.sendall(b'{"return": {}}\n')
        self.qmp_closed.set()

class FakeQEMULauncher:
    """Replaces subprocess.Popen and starts a FakeQEMU instead"""
    def __init__(self, mocker):
        self.mocker = mocker
        self.qmp_delay = 0
        self.qemu = None

    def start(self, cmd, **kwargs):
        self.qemu = FakeQEMU(cmd, self.qmp_delay)
        child = self.mocker.MagicMock()
        child.poll.return_value = None
        child.wait.side_effect = subprocess.TimeoutExpired(cmd='qemu', timeout=0.5)
        return child

@pytest.fixture
def fake_qemu(mocker):
    launcher = FakeQEMULauncher(mocker)
    mocker.patch('subprocess.Popen', side_effect=launcher.start)
    version_mock = mocker.patch('subprocess.run')
    version_mock.return_value.returncode = 0
    version_mock.return_value.stdout = "QEMU emulator version 4.2.1"
    return launcher

@pytest.fixture
def qemu_qmp_socket_driver(qemu_target):
    return QEMUDriver(
        qemu_target,
        "qemu",
        qemu_bin="qemu",
        machine='',
        cpu='',
        memory='',
        kernel='kernel',
        rootfs='rootfs',
        qmp_socket=True)

def test_qemu_qmp_socket_on_off(qemu_target, qemu_qmp_socket_driver, fake_qemu):
    qemu_target.activate(qemu_qmp_socket_driver)

    qemu_qmp_socket_driver.on()
    qemu_qmp_socket_driver.off()

    qemu_target.deactivate(qemu_qmp_socket_driver)

    assert fake_qemu.qemu.qmp_closed.wait(timeout=5)
    assert fake_qemu.qemu.commands == ["qmp_capabilities", "cont", "stop", "system_reset", "quit"]

def test_qemu_qmp_socket_waits_for_qemu(qemu_target, qemu_qmp_socket_driver, fake_qemu):
    fake_qemu.qmp_delay = 0.3
    qemu_target.activate(qemu_qmp_socket_driver)

    assert fake_qemu.qemu.commands == ["qmp_capabilities"]

    qemu_target.deactivate(qemu_qmp_socket_driver)
    assert fake_qemu.qemu.qmp_closed.wait(timeout=5)
