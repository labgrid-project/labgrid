""" tested with Siglent SPD3303X-E, SPD1168X and should be compatible with all SPD3000X series modules """

import pyvisa

def _get_psu(host):
    """Helper to initialize the raw network socket resource session via PyVISA."""
    rm = pyvisa.ResourceManager("@py")
    resource_string = f"TCPIP0::{host}::5025::SOCKET"
    psu = rm.open_resource(resource_string)
    # Siglent scopes and PSUs require explicit newline termination on raw sockets
    psu.read_termination = "\n"
    psu.write_termination = "\n"
    psu.timeout = 5000  # 5 second safety timeout
    return psu

def power_set(host, port, index, value):
    assert port is None
    index = int(index)
    assert 1 <= index <= 2
    value = "ON" if value else "OFF"
    with _get_psu(host) as psu:
        psu.write(f"OUTPUT CH{index},{value}")

def power_get(host, port, index):
    assert port is None
    index = int(index)
    assert 1 <= index <= 2
    with _get_psu(host) as psu:
        state = psu.query("SYSTEM:STATUS?")
    state = int(state, 16)
    bitmask = 1 << (index + 3)
    return bool(state & bitmask)
