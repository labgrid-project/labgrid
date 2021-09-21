""" tested with Siglent SPD3303X-E, and should be compatible with all SPD3000X series modules"""

import vxi11


def power_set(host, index, value):
    index = int(index)
    assert 1 <= index <= 2
    value = "ON" if value else "OFF"
    psu = vxi11.Instrument(host)
    psu.write(f"OUTPUT CH{index},{value}")


def power_get(host, index):
    index = int(index)
    assert 1 <= index <= 2
    psu = vxi11.Instrument(host)
    state = psu.ask("SYSTEM:STATUS?")
    state = int(state, 16)
    bitmask = 1 << (index + 3)
    return bool(state & bitmask)
