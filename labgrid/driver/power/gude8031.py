import requests

# Driver has been tested with:
# * Gude Expert Power Control 8031()
# * Gude Expert Power Control 87-1210-18
#   This device needs to be used in 'Basic Compatible' mode for HTTP GET
#   to be usable. Do not turn on session authentication.

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
    assert 1 <= index <= 20
    # access the web interface...
    value = 1 if value else 0
    r = requests.get(f"http://{host}:{port}/status.json?components=0&cmd=1&p={index}&s={value}")
    r.raise_for_status()


def power_get(host, port, index):
    index = int(index)
    assert 1 <= index <= 20

    # get the component status
    r = requests.get(f"http://{host}:{port}/status.json?components=1")
    r.raise_for_status()

    state = r.json()["outputs"][index - 1]["state"]

    return state
