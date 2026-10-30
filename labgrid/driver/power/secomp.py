"""
Power backend for SECOMP / VALUE IP networked power distribution units.

Tested on the LogiLink PDU8P01 (implementing the SECOMP 0816 chip).

The PDU is controlled via an HTTP endpoint using HTTP basic auth::

    curl --user admin:admin \\
        "http://192.168.10.10/control_outlet.htm?outlet<N>=1&op=<OP>&submit=Apply"

where ``<N>`` is the 0-based outlet index (0..7), ``op=0`` turns the outlet on,
and ``op=1`` turns it off.

Example::

    curl --user admin:admin \\
        "http://192.168.10.10/control_outlet.htm?outlet2=1&op=0&submit=Apply"

The outlet state is read back from ``status.xml``::

    curl --user admin:admin "http://192.168.10.10/status.xml"

which returns an XML document containing ``<outletStat0>`` through
``<outletStat7>`` elements with text ``on`` or ``off``.

Example::

      - NetworkPowerPort:
          host: "http://admin:admin@192.168.10.10"
          model: "secomp"
          index: 7

Reference: https://www.secomp.cz/manualy/19993420_EN.pdf
"""
import time
import xml.etree.ElementTree as ET
import requests

from ..exception import ExecutionError
from ...util import Timeout

DEFAULT_TIMEOUT = 30.0


def power_set(host, port, index, value, timeout=DEFAULT_TIMEOUT):
    """
    host: the base URL including scheme and optional credentials (e.g. 'http://192.168.10.10')
    port: must be None (embedded in host, if non-standard)
    index: the outlet number (1-8)
    value: True (ON) or False (OFF)
    timeout: max seconds to wait for delayed outlet switching
    """
    assert port is None, "Secomp driver expects port to be embedded in the host string"

    index = int(index)
    assert 1 <= index <= 8

    # Secomp 0816 logic: 0 is ON, 1 is OFF
    action_code = 0 if value else 1
    params = {
        f"outlet{index - 1}": 1,
        "op": action_code,
        "submit": "Apply",
    }

    r = requests.get(f"{host}/control_outlet.htm", params=params, timeout=10)
    r.raise_for_status()

    t = Timeout(timeout)
    while True:
        if power_get(host, port, index) == bool(value):
            return
        if t.expired:
            raise ExecutionError(f"Secomp: Timeout waiting for port {index} to become {value}")
        time.sleep(1.0)


def power_get(host, port, index):
    """
    host: the base URL including scheme and optional credentials (e.g. 'http://192.168.10.10')
    port: must be None (embedded in host, if non-standard)
    index: the outlet number (1-8)
    """
    assert port is None, "Secomp driver expects port to be embedded in the host string"

    index = int(index)
    assert 1 <= index <= 8

    r = requests.get(f"{host}/status.xml", timeout=10)
    r.raise_for_status()

    try:
        xml = ET.fromstring(r.content)
    except ET.ParseError as e:
        raise ExecutionError(f"Secomp: failed to parse status.xml: {e}") from e
    outlet = xml.find(f"outletStat{index - 1}")
    if outlet is None or outlet.text is None:
        raise ExecutionError(f"Secomp: could not find status for outlet {index}")
    return outlet.text.strip().lower() == "on"
