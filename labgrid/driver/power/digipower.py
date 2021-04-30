import requests

PORT = 80

def power_set(host, port, index, value):
    index = int(index)
    assert 1 <= index <= 8

    if value:
        cgi = "ons.cgi"
    else:
        cgi = "offs.cgi"

    suffixstring = "0000000000000000"
    r = requests.get(
        f"http://{host}:{port}/{cgi}?led={1 << 8 - index:08b}{suffixstring}",
        auth=("snmp", "1234"),
    )
    r.raise_for_status()


def power_get(host, port, index):
    index = int(index)
    assert 1 <= index <= 8

    r = requests.get(
        f"http://{host}:{port}/status.xml",
        auth=("snmp", "1234"),
    )
    r.raise_for_status()

    state = r.text.split(',')[9 + index]
    return bool(int(state, 2))
