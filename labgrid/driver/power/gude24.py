"""
This driver implements a power port for Gude Power Switches with up to
24 ports.
These switches differ in their API to the previous 8-port switches for set-
and get-commands.

Driver has been tested with:
* Gude Expert Power Control 8080
"""

import re

import requests

from ..exception import ExecutionError


PORT = 80

def power_set(host, port, index, value):
    """
    The gude web-interface uses different pages for the three groups of
    switches. The web-interface always uses the 'correct' page to set a
    value. But commands for all pages are accepted on all pages.
    """
    index = int(index)
    assert 1 <= index <= 24
    # access the web interface...
    value = 1 if value else 0
    response = requests.get(
        f"http://{host}:{port}/ov.html?cmd=1&p={index}&s={value}"
    )

    # Check, that the port is in the desired state
    state = get_state(response, index)
    if state != value:
        raise ExecutionError(f"failed to set port {index} to status {value}")


def power_get(host, port, index):
    """
    Get the status of a port.
    """
    index = int(index)
    assert 1 <= index <= 24
    # get the contents of the main page
    response = requests.get(f"http://{host}:{port}/ov.html")
    state = get_state(response, index)
    return state


def get_state(request, index):
    """
    The status of the ports is made available via a html <meta>-tag using the
    following format:
    <meta http-equiv="powerstate" content="Power Port 1,0">
    Again the status of all ports is made available on all pages.
    """
    request.raise_for_status()

    # Get the power state of a specified index
    # raise an exception if the state cannot be determined.

    for line in request.text.splitlines():
        if line.find(f"content=\"Power Port {index}") > 0:
            if line.find(",0") > 0:
                return False
            if line.find(",1") > 0:
                return True

            raise ExecutionError("failed to parse the port status")

    m = re.search(r"Device is blocked by another user with IP ([^\s<]+)", request.text)
    if m:
        raise ExecutionError(f"device is blocked by another user with IP {m.group(1)}")

    # if we got this far, something is wrong with the website
    raise ExecutionError(f"failed to determine status of power port {index}")
