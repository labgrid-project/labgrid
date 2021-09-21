import re
import requests

PORT = 80

def power_set(host, port, index, value):
    index = int(index)
    assert 1 <= index <= 4
    # access the web interface...
    if value:
        portstring = {1: "1uuu", 2: "u1uu", 3: "uu1u", 4: "uuu1"}
    else:
        portstring = {1: "0uuu", 2: "u0uu", 3: "uu0u", 4: "uuu0"}
    r = requests.get(
        f"http://{host}:{port}/tgi/control.tgi?l=p:admin:admin&p={portstring[index]}"
    )
    r.raise_for_status()


def power_get(host, port, index):
    index = int(index)
    assert 1 <= index <= 4
    # get the contents of the main page
    r = requests.get(f"http://{host}:{port}/tgi/control.tgi?l=p:admin:admin&p=l")
    r.raise_for_status()
    m = re.match(r".*(\d) (\d) (\d) (\d).*", r.text)
    states = {"0": False, "1": True}
    value = m.group(index)
    return states[value]
