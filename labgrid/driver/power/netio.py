import sys
import re
import requests


def power_set(host, index, value):
    index = int(index)
    assert 1 <= index <= 4
    # access the web interface...
    if value:
        portstring = {1: "1uuu", 2: "u1uu", 3: "uu1u", 4: "uuu1"}
    else:
        portstring = {1: "0uuu", 2: "u0uu", 3: "uu0u", 4: "uuu0"}
    r = requests.get(
        "http://{}/tgi/control.tgi?l=p:admin:admin&p={}".
        format(host, portstring[index])
    )
    r.raise_for_status()


def power_get(host, index):
    index = int(index)
    assert 1 <= index <= 4
    # get the contents of the main page
    r = requests.get("http://" + host + "/tgi/control.tgi?l=p:admin:admin&p=l")
    r.raise_for_status()
    m = re.match(".*(\d) (\d) (\d) (\d).*", r.text)
    states = {"0": False, "1": True}
    value = m.group(index)
    return states[value]
