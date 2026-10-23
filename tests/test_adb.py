import subprocess
import sys
import types

from labgrid.resource.adb import NetworkADBDevice, NetworkUSBADBDevice, USBADBDevice
from labgrid.driver.adb import ADBDriver
from labgrid.remote.exporter import ADBExport
from labgrid.remote.client import ClientSession


def test_adb_resources_create(target):
    usb = USBADBDevice(target, "usb", serialno="ABCDEF123456")
    assert usb.serialno == "ABCDEF123456"

    net_usb = NetworkUSBADBDevice(target, "netusb", host="192.168.1.10", serialno="ABCDEF123456", port=5555)
    assert net_usb.host == "192.168.1.10"
    assert net_usb.port == 5555

    net = NetworkADBDevice(target, "net", host="192.168.1.10", port=5555)
    assert net.host == "192.168.1.10"
    assert net.port == 5555


def test_adb_driver_bindings_and_accepts_resources(target):
    binding_set = ADBDriver.bindings["device"]
    assert "USBADBDevice" in binding_set
    assert "NetworkUSBADBDevice" in binding_set
    assert "NetworkADBDevice" in binding_set

    USBADBDevice(target, "adb", serialno="ABCDEF123456")
    driver = ADBDriver(target, "adbdrv")
    assert driver.device is not None


def test_adb_export(target):
    export = ADBExport({
        "cls": "USBADBDevice",
        "params": {"serialno": "ABCDEF123456"},
        "acquired": None,
        "avail": True,
    })
    assert export.data["cls"] == "NetworkUSBADBDevice"
    assert export.local.serialno == "ABCDEF123456"


def test_client_adb_devices_not_argparse_error():
    result = subprocess.run(
        [sys.executable, "-m", "labgrid.remote.client", "adb", "devices"],
        capture_output=True,
    )
    # argparse usage errors (e.g. "invalid choice") always exit with code 2
    assert result.returncode != 2


def test_client_adb_scrcpy_not_argparse_error():
    result = subprocess.run(
        [sys.executable, "-m", "labgrid.remote.client", "adb", "scrcpy"],
        capture_output=True,
    )
    assert result.returncode != 2


def test_client_adb_scrcpy_delegation(mocker):
    session = object.__new__(ClientSession)
    session.get_acquired_place = lambda: types.SimpleNamespace(name="test")
    mock_target = types.SimpleNamespace(resources=[])
    session._get_target = lambda place: mock_target
    session.args = types.SimpleNamespace(name=None, adb_args=["scrcpy", "--extra"], leftover=None)

    mock_scrcpy = mocker.patch.object(ClientSession, "scrcpy")
    session.adb()

    assert session.args.leftover == ["--extra"]
    mock_scrcpy.assert_called_once()


def test_client_adb_normal_command(mocker):
    session = object.__new__(ClientSession)
    session.get_acquired_place = lambda: types.SimpleNamespace(name="test")
    mock_target = types.SimpleNamespace(resources=[])
    session._get_target = lambda place: mock_target
    session.args = types.SimpleNamespace(name=None, adb_args=["devices"])

    mock_run = mocker.patch("labgrid.remote.client.subprocess.run")
    session.adb()

    mock_run.assert_called_once()
    assert "devices" in mock_run.call_args[0][0]
