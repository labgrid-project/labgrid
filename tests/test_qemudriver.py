import pytest

from labgrid.driver import QEMUDriver
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
def qemu_driver(qemu_target):
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
    popen_mock.return_value.wait.return_value = 0
    popen_mock.return_value.stdout.readline.return_value = b"""
    {
      "QMP": {
        "version": {}
      },
      "return": {}
    }
    """

    select_mock = mocker.patch('select.select')
    select_mock.return_value = True, None, None

    socket_mock = mocker.patch('socket.socket')
    socket_mock.return_value.accept.return_value = mocker.MagicMock(), ''

@pytest.fixture
def qemu_version_mock(mocker):
    run_mock = mocker.patch('subprocess.run')
    run_mock.return_value.returncode = 0
    run_mock.return_value.stdout = "QEMU emulator version 4.2.1"

def test_qemu_instance(qemu_target, qemu_driver):
    assert (isinstance(qemu_driver, QEMUDriver))

def test_qemu_activate_deactivate(qemu_target, qemu_driver, qemu_version_mock):
    qemu_target.activate(qemu_driver)
    qemu_target.deactivate(qemu_driver)

def test_qemu_on_off(qemu_target, qemu_driver, qemu_mock, qemu_version_mock):
    qemu_target.activate(qemu_driver)

    qemu_driver.on()
    qemu_driver.off()

    qemu_target.deactivate(qemu_driver)

def test_qemu_read_write(qemu_target, qemu_driver, qemu_mock, qemu_version_mock):
    qemu_target.activate(qemu_driver)

    qemu_driver.on()
    qemu_driver.read()
    qemu_driver.read(max_size=10)
    qemu_driver.write(b'abc')

    qemu_target.deactivate(qemu_driver)
