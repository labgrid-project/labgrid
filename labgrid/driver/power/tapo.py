"""Driver for controlling TP-Link Tapo smart plugs and power strips.

This module provides functionality to control TP-Link Tapo smart power devices through
the kasa library. It supports both single socket devices (like P100) and multi-socket
power strips (like P300).

Features:
- Environment-based authentication using KASA_USERNAME and KASA_PASSWORD
- Support for both single and multi-socket devices

Requirements:
- Valid TP-Link cloud credentials (username/password)
"""

import asyncio
import os

import kasa
from kasa import Credentials, Device, DeviceConfig, DeviceConnectionParameters, DeviceEncryptionType, DeviceFamily
from packaging.version import parse


def _using_old_kasa_api() -> bool:
    target_kasa_version = parse("0.10.0")
    current_kasa_version = parse(kasa.__version__)
    return current_kasa_version < target_kasa_version


def _get_credentials() -> Credentials:
    username = os.environ.get("KASA_USERNAME")
    password = os.environ.get("KASA_PASSWORD")
    if username is None or password is None:
        raise EnvironmentError("KASA_USERNAME or KASA_PASSWORD environment variable not set")
    return Credentials(username=username, password=password)


def _get_connection_type() -> DeviceConnectionParameters:
    # API changed between versions 0.9.1 and 0.10.0 of python-kasa
    if _using_old_kasa_api():
        return DeviceConnectionParameters(
            device_family=DeviceFamily.SmartTapoPlug,
            encryption_type=DeviceEncryptionType.Klap,
            https=False,
            login_version=2,
        )
    # http_port parameter exists in new kasa (>= 0.10.0) API but not in old versions (<= 0.9.1)
    # pylint: disable-next=unexpected-keyword-arg
    return DeviceConnectionParameters(
        device_family=DeviceFamily.SmartTapoPlug,
        encryption_type=DeviceEncryptionType.Klap,
        https=False,
        login_version=2,
        http_port=80,
    )


def _get_device_config(host: str) -> DeviceConfig:
    # Same as with `_get_connection_type` - python-kasa API changed
    if _using_old_kasa_api():
        # uses_http parameter exists in old kasa (<= 0.9.1) API but not in new versions (>= 0.10.0)
        # pylint: disable-next=unexpected-keyword-arg
        return DeviceConfig(
            host=host, credentials=_get_credentials(), connection_type=_get_connection_type(), uses_http=True
        )  # type: ignore[call-arg]
    return DeviceConfig(host=host, credentials=_get_credentials(), connection_type=_get_connection_type())


async def _power_set(host: str, port: str, index: str, value: bool) -> None:
    """We embed the coroutines in an `async` function to minimise calls to `asyncio.run`"""
    assert port is None
    index = int(index)
    device = await Device.connect(config=_get_device_config(host))
    await device.update()

    if device.children:
        assert len(device.children) > index, "Trying to access non-existent plug socket on device"

    target = device if not device.children else device.children[index]
    if value:
        await target.turn_on()
    else:
        await target.turn_off()
    await device.disconnect()


def power_set(host: str, port: str, index: str, value: bool) -> None:
    asyncio.run(_power_set(host, port, index, value))


async def _power_get(host: str, port: str, index: str) -> bool:
    assert port is None
    index = int(index)
    device = await Device.connect(config=_get_device_config(host))
    await device.update()

    pwr_state: bool
    # If the device has no children, it is a single plug socket
    if not device.children:
        pwr_state = device.is_on
    else:
        assert len(device.children) > index, "Trying to access non-existent plug socket on device"
        pwr_state = device.children[index].is_on
    await device.disconnect()
    return pwr_state


def power_get(host: str, port: str, index: str) -> bool:
    return asyncio.run(_power_get(host, port, index))
