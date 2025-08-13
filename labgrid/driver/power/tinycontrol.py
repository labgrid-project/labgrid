""" A driver to control the Tinycontrol IP Power Socket 6G10A v2
    Reference: https://tinycontrol.pl/media/documents/manual_IP_Power_Socket__6G10A_v2_LANLIS-010-015_En-1.pdf

    Example configuration to use port #3 on a device with URL 'http://172.17.180.53:9999/'

    NetworkPowerPort:
      model: tinycontrol
      host: 'http://172.17.180.53:9999/'
      index: 3
"""

from urllib.parse import urljoin
import xml.etree.ElementTree as ET

import requests

def power_set(host, port, index, value):
    assert port is None

    index = int(index)
    value = 1 if value else 0
    r = requests.get(urljoin(host, f"/outs.cgi?out{index}={value}"))
    r.raise_for_status()


def power_get(host, port, index):
    assert port is None

    index = int(index)
    r = requests.get(urljoin(host, "/st0.xml"))
    r.raise_for_status()
    root = ET.fromstring(r.text)
    output = root.find(f"out{index}")
    return output.text == '1'
