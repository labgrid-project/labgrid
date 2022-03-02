"""Rest interface for controlling power port, using PUT / GET on a URL.

  NetworkPowerPort:
      model: rest
      host: 'http://192.168.0.42/relay/{index}/value'
      index: 3

  Will do a GET request to http://192.168.0.42/relay/3/value to get current
  relay state, expecting a response of either '0' (relay off) or '1' (relay
  on), and a PUT request to http://192.168.0.42/relay/3/value with request
  data of '0' or '1' to change relay state.

"""

import requests

def power_set(host, port, index, value):
    assert port is None
    value = b"1" if value else b"0"
    r = requests.put(host.format(index=index), data=value)
    r.raise_for_status()

def power_get(host, port, index):
    assert port is None
    r = requests.get(host.format(index=index))
    r.raise_for_status()
    return r.text == "1"
