import subprocess

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

def test_add_usb_network_device(qemu_target, qemu_driver, qemu_mock, qemu_version_mock, mocker):
    qemu_target.activate(qemu_driver)

    qemu_driver.on()
    qemu_driver.qmp.execute = mocker.MagicMock(return_value={})
    qemu_driver.add_usb_network_device()
    qemu_driver.qmp.execute.assert_any_call("netdev_add", {"type": "user", "id": "usbnet"})
    qemu_driver.qmp.execute.assert_any_call("device_add", {"driver": "usb-net", "id": "usb-net-0", "netdev": "usbnet", "bus": "xhci.0"})

    qemu_target.deactivate(qemu_driver)


def test_add_usb_network_device_custom_args(qemu_target, qemu_driver, qemu_mock, qemu_version_mock, mocker):
    qemu_target.activate(qemu_driver)

    qemu_driver.on()
    qemu_driver.qmp.execute = mocker.MagicMock(return_value={})
    qemu_driver.add_usb_network_device(device_id="usb-net-1", netdev="mynet", bus="xhci.0")
    qemu_driver.qmp.execute.assert_any_call("netdev_add", {"type": "user", "id": "mynet"})
    qemu_driver.qmp.execute.assert_any_call("device_add", {"driver": "usb-net", "id": "usb-net-1", "netdev": "mynet", "bus": "xhci.0"})

    qemu_target.deactivate(qemu_driver)


def test_remove_usb_network_device(qemu_target, qemu_driver, qemu_mock, qemu_version_mock, mocker):
    qemu_target.activate(qemu_driver)

    qemu_driver.on()
    qemu_driver.qmp.execute = mocker.MagicMock(return_value={})
    qemu_driver.add_usb_network_device()
    qemu_driver.remove_usb_network_device()
    qemu_driver.qmp.execute.assert_any_call("device_del", {"id": "usb-net-0"})
    qemu_driver.qmp.execute.assert_any_call("netdev_del", {"id": "usbnet"})

    qemu_target.deactivate(qemu_driver)
