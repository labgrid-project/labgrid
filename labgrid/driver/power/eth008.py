"""
This driver implements a power port for the robot electronics 8 relay
outputs board.

Driver has been tested with:
* ETH008 - 8 relay outputs
"""

import requests
from ..exception import ExecutionError

PORT = 80

def power_set(host, port, index, value):
    index = int(index)
    assert 1 <= index <= 8
    # access the web interface...
    value_str = "A" if value else "I"
    response = requests.get(
        f"http://{host}:{port}/io.cgi?DO{value_str}{index}"
    )
    response.raise_for_status()
    
    # Check, that the port is in the desired state
    state = get_state(response, index)
    if state != value:
        raise ExecutionError(f"failed to set port {index} to status {value}")

def power_get(host, port, index):
    index = int(index)
    assert 1 <= index <= 8
    # get the contents of the main page
    response = requests.get(f"http://{host}:{port}/io.cgi?relay")
    
    response.raise_for_status()
    state = get_state(response, index)
    return state

def get_state(request, index):
    value = request.text.split()[1][index-1]
    return bool(int(value))
