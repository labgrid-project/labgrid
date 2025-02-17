"""Tested with TAPO P100, and should be compatible with any TAPO smart plug supported by kasa

There is a list of supported devices in python-kasa package official documentation.
https://python-kasa.readthedocs.io/en/stable/SUPPORTED.html#tapo-devices

"""

import asyncio
import os

from kasa import (
    Credentials,
    DeviceConfig,
    DeviceConnectionParameters,
    DeviceEncryptionType,
    DeviceFamily,
    SmartProtocol,
    smart,
    transports,
)

connection_type = DeviceConnectionParameters(
    device_family=DeviceFamily.SmartTapoPlug, encryption_type=DeviceEncryptionType.Klap, login_version=2
)


def get_credentials():
    username = os.environ.get("KASA_USERNAME")
    password = os.environ.get("KASA_PASSWORD")
    if username is None or password is None:
        raise ValueError(
            "Username and password cannot be None.Set KASA_USERNAME and KASA_PASSWORD environment variables"
        )
    return Credentials(username=username, password=password)


async def _power_set(host, port, index, value):
    assert port is None
    config = DeviceConfig(host=host, credentials=get_credentials(), connection_type=connection_type)
    protocol = SmartProtocol(transport=transports.KlapTransportV2(config=config))

    device = smart.SmartDevice(host=host, config=config, protocol=protocol)

    try:
        await device.update()

        if value:
            await device.turn_on()
        else:
            await device.turn_off()
    except Exception as e:
        print(f"An error occurred while setting power: {e}")
    finally:
        await device.disconnect()


def power_set(host, port, index, value):
    asyncio.run(_power_set(host, port, index, value))


async def _power_get(host, port, index):
    assert port is None
    config = DeviceConfig(host=host, credentials=get_credentials(), connection_type=connection_type)
    protocol = SmartProtocol(transport=transports.KlapTransportV2(config=config))

    device = smart.SmartDevice(host=host, config=config, protocol=protocol)
    try:
        await device.update()
        return device.is_on
    except Exception as e:
        print(f"An error occurred while getting power: {e}")
    finally:
        await device.disconnect()


def power_get(host, port, index):
    return asyncio.run(_power_get(host, port, index))
