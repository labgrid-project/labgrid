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

def power_show(host, port, index):
    assert port is None
    index = int(index)
    assert 1 <= index <= 2
    with _get_psu(host) as psu:
        v_measured = psu.query(f"MEAS:VOLT? CH{index}")
        a_measured = psu.query(f"MEAS:CURR? CH{index}")
        w_measured = psu.query(f"MEAS:POWE? CH{index}")
        v_set = psu.query(f"CH{index}:VOLT?")
        a_set = psu.query(f"CH{index}:CURR?")
    return {
        "voltage": float(v_measured),
        "amps": float(a_measured),
        "watts": float(w_measured),
        "v_limit": float(v_set),
        "a_limit": float(a_set)
    }

def power_watts(host, port, index):
    """Read the power (in watts) measured by the device on the given channel.

    The PSU reports true power directly, so this avoids errors from
    multiplying voltage and current sampled at slightly different times.
    """
    assert port is None
    index = int(index)
    assert 1 <= index <= 2
    with _get_psu(host) as psu:
        w_measured = psu.query(f"MEAS:POWE? CH{index}")
    return float(w_measured)

def power_voltage(host, port, index, voltage):
    assert port is None
    index = int(index)
    assert 1 <= index <= 2
    with _get_psu(host) as psu:
        psu.write(f"CH{index}:VOLT {voltage}")

def power_amps(host, port, index, amps):
    assert port is None
    index = int(index)
    with _get_psu(host) as psu:
        psu.write(f"CH{index}:CURR {amps}")

