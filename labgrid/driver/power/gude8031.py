import requests
import json
from ..exception import ExecutionError

# Driver has been tested with:
# Gude Expert Power Control 8031()

# Components Parameter is static, defines how to interact whith power controller

PORT = 80

def power_set(host, port, index, value):
    index = int(index)
    assert 1 <= index <= 8
    # access the web interface...
    value = 1 if value else 0
    r = requests.get(
        "http://{}:{}//status.json?components=769&cmd=1&p={}&s={}".format(host, port, index, value)
    )
    r.raise_for_status()

def power_get(host, port, index):
    index = int(index)
    assert 1 <= index <= 8

    # get the component status
    r = requests.get("http://{}:{}/status.json?components=575235".format(host, port))
    r.raise_for_status()

    state = r.json()['outputs'][index - 1]['state']

    return state
