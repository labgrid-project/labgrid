""" Simple rest interface for Power Port. Used for ex. misc Raspberry Pi configs
    Author: Kjeld Flarup <kfa@deif.com>

    The URL given in hosts in exporter.yaml must replace {value} with '0' or '1'
    It is optional whether to use {index} or not.

  NetworkPowerPort:
      model: simplerest
      host: 'http://172.17.180.53:9999/relay/{index}/{value}'
      index: 0
"""

import requests

def power_set(host, index, value):
    index = int(index)
    value = 1 if value else 0
    requests.get(host.format(value=value, index=index))

def power_get(host, index):
    index = int(index)
    # remove trailing /
    r = requests.get(host.format(value='', index=index).rstrip('/'))
    r.raise_for_status()
    return r.text == '1'
