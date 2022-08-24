import pytest

from labgrid.resource import NetworkService
from labgrid.driver import QEMUDriver, QEMUNetworkService
from labgrid import Environment, target_factory


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
def qemu_driver_user(qemu_target):
    q = QEMUDriver(
        qemu_target,
        "qemu",
        qemu_bin="qemu",
        machine="",
        cpu="",
        memory="",
        boot_args="",
        extra_args="",
        kernel="kernel",
        rootfs="rootfs",
        nic="user",
    )
    return q


@pytest.fixture
def qemu_driver_tap(qemu_target):
    q = QEMUDriver(
        qemu_target,
        "qemu",
        qemu_bin="qemu",
        machine="",
        cpu="",
        memory="",
        boot_args="",
        extra_args="",
        kernel="kernel",
        rootfs="rootfs",
        nic="tap",
    )
    return q


@pytest.fixture
def qemu_network_service(qemu_target):
    q = QEMUNetworkService(
        qemu_target,
        "test-network-service1",
        address="10.10.0.5",
        username="root",
        port=123,
        password="secret",
    )
    return q


@pytest.fixture
def qemu_mock(mocker):
    popen_mock = mocker.patch("subprocess.Popen")
    popen_mock.return_value.wait.return_value = 0
    popen_mock.return_value.stdout.readline.return_value = b"""
    {
      "QMP": {
        "version": {}
      },
      "return": {}
    }
    """

    select_mock = mocker.patch("select.select")
    select_mock.return_value = True, None, None

    socket_mock = mocker.patch("socket.socket")
    socket_mock.return_value.accept.return_value = mocker.MagicMock(), ""


def test_qemu_network_service_user(
    qemu_target,
    qemu_driver_user,
    qemu_network_service,
    qemu_mock,
):
    qemu_target.activate(qemu_network_service)
    qemu_driver_user.on()

    ns = qemu_network_service.get_network_service()
    assert isinstance(ns, NetworkService)

    qemu_target.activate(ns)

    assert ns.username == qemu_network_service.username
    assert ns.password == qemu_network_service.password
    assert ns.address == "127.0.0.1"
    assert ns.port != qemu_network_service.port

    qemu_target.deactivate(qemu_network_service)


def test_qemu_network_service_nic(
    qemu_target,
    qemu_driver_tap,
    qemu_network_service,
    qemu_mock,
):
    qemu_target.activate(qemu_network_service)
    qemu_driver_tap.on()

    ns = qemu_network_service.get_network_service()
    assert isinstance(ns, NetworkService)

    qemu_target.activate(ns)

    assert ns.username == qemu_network_service.username
    assert ns.password == qemu_network_service.password
    assert ns.address == qemu_network_service.address
    assert ns.port == qemu_network_service.port

    qemu_target.deactivate(qemu_network_service)
