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
    portstring = {
        "1": "10000000",
        "2": "01000000",
        "3": "00100000",
        "4": "00010000",
        "5": "00001000",
        "6": "00000100",
        "7": "00000010",
        "8": "00000001",
    }
    r = requests.get(
        "http://{}:{}/{}?led={}".format(host, port, cgi, portstring[index] + suffixstring),
        auth=("snmp", "1234"),
    )
    r.raise_for_status()


def power_get(host, port, index):
    index = int(index)
    assert 1 <= index <= 8

    # get the contents of the status page
    r = requests.get("http://{}:{}/status.xml".format(host, port), auth=("snmp", "1234"))
    r.raise_for_status()
    states = {"0": False, "1": True}
    ports = {
        "1": 10,
        "2": 11,
        "3": 12,
        "4": 13,
        "5": 14,
        "6": 15,
        "7": 16,
        "8": 17
    }
    return states[r.content.split(',')[ports[index]]]
