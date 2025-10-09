import requests


# Driver has been tested with:
# * Gude Expert Power Control 8031-1
# * Gude Expert Power Control 8316-1
# * Gude Expert Power Control 87-1210-18
# According to the manual it also should work with:
# * Gude Expert Power Control 8316
#
# This device needs to be used in 'Basic Compatible' mode for HTTP GET
# to be usable. Do not turn on session authentication.
#
# HTTP-GET API is defined in the Gude EPC-HTTP-Interface specification:
# http://wiki.gude.info/EPC_HTTP_Interface
#
# The `components=<N>` parameter defines which status information are
# included into the returned JSON.
# * `components=0` happily returns an empty response but still switches the
#   outputs as requested.
# * `components=1` only includes the output's state into the JSON.

PORT = 80


def power_set(host, port, index, value):
    index = int(index)
    upper_limit = count_ports(host, port)
    assert 1 <= index <= upper_limit, f'index ({index}) out of port range (1-{upper_limit})'
    # access the web interface...
    value = 1 if value else 0
    r = requests.get(f"http://{host}:{port}/status.json?components=0&cmd=1&p={index}&s={value}")
    r.raise_for_status()


def power_get(host, port, index):
    index = int(index)

    # get the component status
    r = requests.get(f"http://{host}:{port}/status.json?components=1")
    r.raise_for_status()

    body = r.json() 
    assert 1 <= index <= len(body["outputs"]), f'index ({index}) out of port range (1-{len(body["outputs"])})'
    state = body["outputs"][index - 1]["state"]

    return state


def count_ports(host, port):
    r = requests.get(f"http://{host}:{port}/status.json?components=1")
    r.raise_for_status()
    return len(r.json()["outputs"])