import logging
from unittest.mock import Mock, patch

import pytest

from labgrid.driver.sigrokdriver import SigrokDriver, SigrokPowerDriver
from labgrid.resource.common import NetworkResource, Resource
from labgrid.resource.remote import NetworkSigrokUSBDevice, NetworkSigrokUSBSerialDevice
from labgrid.resource.udev import SigrokUSBDevice, SigrokUSBSerialDevice

SSH_PREFIX = ["ssh", "example.org", "--"]


def make_driver(driver_cls, resource_cls, *, remote, **fields):
    driver = driver_cls.__new__(driver_cls)
    driver.tool = "sigrok-cli"
    driver.logger = logging.getLogger("test")
    resource = Mock(spec=resource_cls, **fields)
    if remote:
        resource.command_prefix = SSH_PREFIX
        resource.wrap_command.side_effect = lambda command: NetworkResource.wrap_command(resource, command)
    else:
        resource.command_prefix = []
        resource.wrap_command.side_effect = lambda command: Resource.wrap_command(resource, command)
    driver.sigrok = resource
    return driver, resource


def make_power_driver(*, remote):
    resource_cls = NetworkSigrokUSBSerialDevice if remote else SigrokUSBSerialDevice
    driver, resource = make_driver(
        SigrokPowerDriver,
        resource_cls,
        remote=remote,
        driver="manson-hcs-3xxx",
        path="/dev/ttyUSB0",
        channels=None,
        channel_group=None,
    )
    driver.max_voltage = None
    driver.max_current = None
    return driver, resource


POWER_PREFIX = ["sigrok-cli", "-d", "manson-hcs-3xxx:conn=/dev/ttyUSB0"]


@pytest.mark.parametrize(
    "method, args, suffix, output",
    [
        ("on", (), ["--config", "enabled=yes", "--set"], b""),
        ("off", (), ["--config", "enabled=no", "--set"], b""),
        ("set_voltage_target", (3.3,), ["--config", "voltage_target=3.300000", "--set"], b""),
        ("set_current_limit", (0.5,), ["--config", "current_limit=0.500000", "--set"], b""),
        ("get", (), ["--get", "enabled"], b"true"),
        ("measure", (), ["--show"], b"voltage: 3.3\ncurrent: 0.5\n"),
    ],
)
@pytest.mark.parametrize("remote", [False, True])
def test_power_driver_commands(method, args, suffix, output, remote):
    driver, _ = make_power_driver(remote=remote)
    prefix = SSH_PREFIX if remote else []

    with patch("labgrid.driver.sigrokdriver.processwrapper.check_output", return_value=output) as run:
        getattr(SigrokPowerDriver, method).__wrapped__(driver, *args)

    run.assert_called_once_with(prefix + POWER_PREFIX + suffix)


def test_power_driver_get_and_measure_results():
    driver, _ = make_power_driver(remote=True)

    with patch("labgrid.driver.sigrokdriver.processwrapper.check_output", return_value=b"false"):
        assert SigrokPowerDriver.get.__wrapped__(driver) is False

    with patch(
        "labgrid.driver.sigrokdriver.processwrapper.check_output",
        return_value=b"voltage: 3.3\ncurrent: 0.5\n",
    ):
        assert SigrokPowerDriver.measure.__wrapped__(driver) == {"voltage": 3.3, "current": 0.5}


@pytest.mark.parametrize("remote", [False, True])
def test_analyze_command(remote, tmp_path):
    resource_cls = NetworkSigrokUSBDevice if remote else SigrokUSBDevice
    driver, resource = make_driver(
        SigrokDriver,
        resource_cls,
        remote=remote,
        driver="fx2lafw",
        busnum=1,
        devnum=2,
        channels="D0,D1",
        channel_group=None,
    )
    driver._filename = None
    prefix = SSH_PREFIX if remote else []
    filename = str(tmp_path / "capture.sr")

    with (
        patch("labgrid.driver.sigrokdriver.check_file") as check_file,
        patch("labgrid.driver.sigrokdriver.processwrapper.check_output", return_value=b"") as run,
    ):
        result = SigrokDriver.analyze.__wrapped__(driver, ["-P", "uart"], filename)

    assert result == []
    check_file.assert_called_once_with(filename, resource=resource)
    run.assert_called_once_with(
        prefix
        + [
            "sigrok-cli",
            "-d",
            "fx2lafw:conn=1.2",
            "-C",
            "D0,D1",
            "-i",
            filename,
            "-P",
            "uart",
            "--protocol-decoder-samplenum",
            "-l",
            "4",
        ],
        stderr=None,
    )
