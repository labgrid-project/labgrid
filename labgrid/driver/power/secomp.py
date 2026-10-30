"""
This driver was tested on the model: LogiLink PDU8P01, implementing SECOMP chip.

Reference: https://www.secomp.cz/manualy/19993420_EN.pdf
"""
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urljoin
from ..exception import ExecutionError

def _send_request(host, url_path, params=None):
    """
    Helper to send requests using urljoin and native requests auth handling
    """
    if not host.startswith('http'):
        host = f"http://{host}"
    full_url=urljoin(host, url_path)

    try:
        response = requests.get(full_url, params=params, timeout=10)
        if response.status_code == 401:
            raise ExecutionError(f"Secomp: Authentication failed (401) for {full_url}.")
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        raise ExecutionError(f"Secomp: HTTP Request failed: {e}")

def power_set(host, port, index, value):
    """
    host: the IP or URL, can include credentials
    port: must be None (embedded in host, if non-standard)
    index: the outlet number (1-8)
    value: True (ON) or False (OFF)
    """
    assert port is None, "Secomp driver expects port to be embedded in the host string"

    # Secomp 0816 logic: 0 is ON, 1 is OFF
    action_code = 0 if value else 1
    params = {
        f"outlet{int(index)-1}": 1,
        "op": action_code,
        "submit": "Apply"
    }

    response = _send_request(host, "control_outlet.htm", params=params)
    if "Apply" not in response.text:
        raise ExecutionError(f"Secomp: PDU failed to set port {index}")

def power_get(host, port, index):
    assert port is None, "Secomp driver expects port to be embedded in the host string"

    response = _send_request(host, "status.xml")
    try:
        xml = ET.fromstring(response.content)
        outlet_node = xml.find(f'outletStat{int(index)-1}')
        if outlet_node is None:
            raise ExecutionError(f"Secomp: Could not find status for port {index}")
        return outlet_node.text.lower() == "on"
    except Exception as e:
        raise ExecutionError(f"Secomp: Failed to get status: {e}")
