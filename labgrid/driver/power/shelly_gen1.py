"""Interface for controlling relays of Shelly devices using the Gen 1 API

  NetworkPowerPort:
      model: shelly_gen1
      host: 'http://192.168.0.42'
      index: 0

  Will do a GET request to http://192.168.0.42/relay/0 to get the current
  relay state, and a POST request to http://192.168.0.42/relay/0 with request
  data of 'turn=off' or 'turn=on' to change the relay state.

  Also, see the official Gen 1 Device API documentation:
  https://shelly-api-docs.shelly.cloud/gen1/

"""
import json

import requests

def power_set(host:str, port:int, index:int=0, value:bool=True):
    assert not port
    turn = "on" if value else "off"
    r = requests.post(f"{host}/relay/{index}", data={'turn': turn})
    r.raise_for_status()

def power_get(host:str, port:int, index:int):
    assert not port
    r = requests.get(f"{host}/relay/{index}")
    r.raise_for_status()
    return json.loads(r.text)['ison']
