"""Interface for controlling relays of Shelly devices using the Gen 2+ API

  NetworkPowerPort:
      model: shelly_gen2
      host: 'http://192.168.0.42'
      index: 0

Will do a POST request to http://192.168.0.42/rpc to get the current
relay state or change the state.

Also, see the official Gen 2+ Device API documentation:
https://shelly-api-docs.shelly.cloud/gen2/General/RPCProtocol
"""

import requests


def power_set(host: str, port: int, index: int = 0, value: bool = True):
    assert not port
    payload = {"id": 1, "method": "Switch.Set", "params": {"id": index, "on": value}}
    r = requests.post(f"{host}/rpc", json=payload)
    r.raise_for_status()


def power_get(host: str, port: int, index: int = 0):
    assert not port
    payload = {"id": 1, "method": "Switch.GetStatus", "params": {"id": index}}
    r = requests.post(f"{host}/rpc", json=payload)
    r.raise_for_status()
    return r.json()["result"]["output"]
