import requests

# Driver has been tested with:
# Gude  Expert Power Control 8225-1 - v1.0.6

# HTTP-GET API is defined in the Gude EPC-HTTP-Interface specification:
# http://wiki.gude.info/EPC_HTTP_Interface

PORT = 80


def power_set(host, port, index, value):
    index = int(index)
    assert 1 <= index <= 12

    value = 1 if value else 0
    r = requests.get(
        f"http://{host}:{port}/ov.html?cmd=1&p={index}&s={value}"
    )
    r.raise_for_status()


def power_get(host, port, index):
    index = int(index)
    assert 1 <= index <= 12

    r = requests.get(f"http://{host}:{port}/statusjsn.js?components=1")
    r.raise_for_status()

    state = r.json()['outputs'][index - 1]['state']

    return state
