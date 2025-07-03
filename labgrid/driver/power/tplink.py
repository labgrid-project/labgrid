""" Tested with TP Link KP303, and should be compatible with any strip supported by kasa """

import asyncio
from kasa import DeviceType, Discover
from kasa.iot import IotStrip


async def _power_set(host, port, index, value):
    """We embed the coroutines in an `async` function to minimise calls to `asyncio.run`"""
    assert port is None
    index = int(index)
    dev = await Discover.discover_single(host)
    if dev.device_type == DeviceType.Strip:
        iotstrip = IotStrip(host)
        await iotstrip.update()
        assert (
            len(iotstrip.children) > index
        ), "Trying to access non-existant plug socket on strip"
        if value:
            await iotstrip.children[index].turn_on()
        else:
            await iotstrip.children[index].turn_off()
    elif dev.device_type == DeviceType.Plug:
        await dev.update()
        if value:
            await dev.turn_on()
        else:
            await dev.turn_off()


def power_set(host, port, index, value):
    asyncio.run(_power_set(host, port, index, value))

async def _power_get(host, port, index):
    assert port is None
    index = int(index)
    dev = await Discover.discover_single(host)
    if dev.device_type == DeviceType.Strip:
        iotstrip = IotStrip(host)
        await iotstrip.update()
        assert (
            len(iotstrip.children) > index
        ), "Trying to access non-existant plug socket on strip"
        return iotstrip.children[index].is_on
    elif dev.device_type == DeviceType.Plug:
        await dev.update()
        return dev.is_on

def power_get(host, port, index):
    return asyncio.run(_power_get(host, port, index))
