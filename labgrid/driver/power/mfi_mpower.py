"""
    Controls the *Ubiquity mFi mPower* Power Strip with Ethernet and Wi-Fi connectivity via HTTP.
    Reference: https://dl.ubnt.com/guides/mfi/mFi_mPower_PRO_US_QSG.pdf

    Example configuration to use port #3 on a device with URL 'http://172.17.180.53/'
    with the default credentials ('ubnt' for both username and password):

    NetworkPowerPort:
      model: mfi_mpower
      host: 'http://172.17.180.53/'
      index: 3

    Custom credentials can be provided in the URL itself:

    NetworkPowerPort:
      model: mfi_mpower
      host: 'http://username:password@172.17.180.53/'
      index: 3
"""

from typing import Tuple
from urllib.parse import urlparse, urljoin

import requests

from ..exception import ExecutionError


def login(s: requests.Session, base_url: str, credentials: dict) -> None:

    # We need to first fetch the base url to satisfy the Cookie Monster
    s.get(base_url)

    s.post(urljoin(base_url, '/login.cgi'),
        data=dict(username=credentials['username'], password=credentials['password']))


# Obtain credentials and repack base_url if needed
def get_credentials(base_url: str) -> Tuple[str, dict]:
    base_url = urlparse(base_url)

    if base_url.username is None or base_url.password is None:
        credentials = dict(username='ubnt', password='ubnt')
    else:
        credentials = dict(username=base_url.username, password=base_url.password)
        base_url._replace(netloc=base_url.netloc.replace(f'{base_url.username}:{base_url.password}@', ''))

    base_url = base_url.geturl()
    return (base_url, credentials)


def power_set(host, port, index, value):
    index = int(index)
    value = 1 if value else 0

    (base_url, credentials) = get_credentials(host)

    s = requests.Session()

    login(s, base_url, credentials)
    r = s.put(urljoin(base_url, f'/sensors/{index}/'), data=dict(output=value))
    if r.status_code == 200 and r.headers['Content-Type'] == 'application/json':
        j = r.json()
        if j['status'] != 'success':
            raise ExecutionError(f"unexpected API status code: '{j['status']}', response JSON: {j}")
    else:
        raise ExecutionError(f"unexpected http response: code {r.status_code}, content type '{r.headers['Content-Type']}' and content: '{r.text}'")


def power_get(host, port, index):
    index = int(index)

    s = requests.Session()

    (base_url, credentials) = get_credentials(host)

    login(s, base_url, credentials)

    r = s.get(urljoin(base_url, '/mfi/sensors.cgi'))
    if r.status_code == 200 and r.headers['Content-Type'] == 'application/json':
        j = r.json()
        if j['status'] != 'success':
            raise ExecutionError(f"unexpected API status code: '{j['status']}', response JSON: {j}")

        port = next(filter(lambda s: s['port'] == index, j['sensors']), None)
        if port is None:
            raise ExecutionError(f"port index '{index}' not found, available indices: '{[s['port'] for s in j['sensors']]}'")

        if port['output'] == 0:
            return False
        elif port['output'] == 1:
            return True
        else:
            raise ExecutionError("unexpected port output value: '{port['output']}'")
    else:
        raise ExecutionError(f"unexpected http response: code {r.status_code}, content type '{r.headers['Content-Type']}' and content: '{r.text}'")

    return False

