"""
This driver was tested on the model: LogiLink PDU8P01
but should be working on all similar devices implementing this SECOMP chip.

The driver is pretty simply and generic, it requires http(s), needs provided
authentication and uses a '0' for on.
"""
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
from ..exception import ExecutionError

def _send_request(host, url_path, params=None):
    """
    Helper to handle host string which might have credentials stripped
    or scheme changed
    """
    if not host.startswith('http'):
        host = f"http://{host}"
    parsed = urlparse(host)

    base_url = f"{parsed.scheme}://{parsed.netloc.split('@')[-1]}"
    full_url = f"{base_url}/{url_path}"

    auth = None
    if parsed.username and parsed.password:
        auth = (parsed.username, parsed.password)

    try:
        response = requests.get(full_url, params=params, auth=auth, timeout=10)
        if response.status_code == 401:
            raise ExecutionError(f"Secomp: Authentication failed (401) for {full_url}. Check YAML credentials.")
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        raise ExecutionError(f"Secomp: HTTP Request failed: {e}")

def power_set(host, port, index, value):
    """
    host: the IP or URL
    port: the TCP port (usually 80)
    index: the outlet number (1-8)
    value: True (ON) or False (OFF)
    """
    # Secomp 0816 logic: 0 is ON, 1 is OFF
    action_code = 0 if value else 1
    params = {
        f"outlet{int(index)-1}": 1,
        "op": action_code,
        "submit": "Apply"
    }

    try:
        response = _send_request(host, "control_outlet.htm", params=params)
        if "Apply" not in response.text:
            raise ExecutionError(f"Secomp: PDU failed to set port {index}")
    except requests.exceptions.RequestException as e:
        raise ExecutionError(f"Secomp: HTTP Request failed: {e}")

def power_get(host, port, index):
    response = _send_request(host, "status.xml")
    try:
        xml = ET.fromstring(response.content)
        outlet_node = xml.find(f'outletStat{int(index)-1}')
        if outlet_node is None:
            raise ExecutionError(f"Secomp: Could not find status for port {index}")
        return outlet_node.text.lower() == "on"
    except Exception as e:
        raise ExecutionError(f"Secomp: Failed to get status: {e}")
