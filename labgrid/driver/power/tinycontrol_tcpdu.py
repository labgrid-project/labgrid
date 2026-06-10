"""A driver to control the Tinycontrol tcPDU
Reference: https://docs.tinycontrol.pl/en/tcpdu/api/commands

Example configuration to use port #3 on a device with URL 'http://172.17.180.53/'

NetworkPowerPort:
  model: tinycontrol_tcpdu
  host: 'http://172.17.180.53'
  index: 3
"""

from urllib.parse import urljoin

import requests


def power_set(host, port, index, value):
    assert port is None

    index = int(index)
    value = 1 if value else 0
    r = requests.get(urljoin(host, f"/api/v1/save/?out{index}={value}"))
    r.raise_for_status()


def power_get(host, port, index):
    assert port is None

    index = int(index)
    r = requests.get(urljoin(host, "/api/v1/read/status/?outValues"))
    r.raise_for_status()
    json_decoded = r.json()
    return json_decoded[f"out{index}"] == 1
