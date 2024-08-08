"""Tested with Aten PE6216.

HTTP API is defined by in the aten PDU PE6216 specification:
https://assets.aten.com/product/manual/Restful-API-Guide-for-PDU_2022-11-18.pdf
"""
import re
import requests

PORT = 80

MIN_OUTLET_INDEX = 1
MAX_OUTLET_INDEX = 16
headers = {'Content-Type': 'application/x-www-form-urlencoded'}

def power_set(host, port, index, value):
    index = int(index)
    assert MIN_OUTLET_INDEX <= index <= MAX_OUTLET_INDEX
    value = 'on' if value else 'off'

    requests.post(
        f'http://{host}:{port}/api/outlet/relay',
        headers=headers,
        data={
            'usr': 'administrator',
            'pwd': 'password',
            'index': index,
            'method': value,
        }
    )


def power_get(host, port, index):
    index = int(index)
    assert MIN_OUTLET_INDEX <= index <= MAX_OUTLET_INDEX

    response = requests.get(
        f'http://{host}:{port}/api/outlet/relay',
        headers=headers,
        params={
            'usr': 'administrator',
            'pwd': 'password',
            'index': index,
        }
    )

    m = re.search( r'<\d+>(?P<state>(ON|OFF|PENDING))<.*', response.text)
    if m is None:
        raise RuntimeError('PE6216: could not match reponse')
    return m.group('state') == 'ON'
