import requests

from ..exception import ExecutionError


def power_set(host, index, value):
    index = int(index)
    assert 1 <= index <= 8
    # access the web interface...
    value = 1 if value else 0
    r = requests.get(
        "http://{}/switch.html?cmd=1&p={}&s={}".format(host, index, value)
    )
    r.raise_for_status()


def power_get(host, index):
    index = int(index)
    assert 1 <= index <= 8
    # get the contents of the main page
    r = requests.get("http://{}/".format(host))
    r.raise_for_status()
    for line in r.text.splitlines():
        power_pattern = "Power Port {}</td>".format(index)
        switch_patern = "SwitchPort {}</td>".format(index)
        if line.find(power_pattern) > 0 or line.find(switch_patern) > 0:
            if line.find("OFF") > 0:
                return False
            elif line.find("ON") > 0:
                return True
            else:
                raise ExecutionError("failed to parse the port status")
    # if we got this far, something is wrong with the website
    raise ExecutionError("failed to find the port")
