""" Tested with TP Link KP303, and should be compatible with any strip supported by kasa """

import asyncio
from kasa.iot import IotStrip


async def _power_set(host, port, index, value):
    """We embed the coroutines in an `async` function to minimise calls to `asyncio.run`"""
    assert port is None
    index = int(index)
    strip = IotStrip(host)
    await strip.update()
    assert (
        len(strip.children) > index
    ), "Trying to access non-existant plug socket on strip"
    if value is True:
        await strip.children[index].turn_on()
    elif value is False:
        await strip.children[index].turn_off()


def power_set(host, port, index, value):
    asyncio.run(_power_set(host, port, index, value))


def power_get(host, port, index):
    assert port is None
    index = int(index)
    strip = IotStrip(host)
    asyncio.run(strip.update())
    assert (
        len(strip.children) > index
    ), "Trying to access non-existant plug socket on strip"
    return strip.children[index].is_on
