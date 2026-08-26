"""Power backend for the Minuteman RPM1521 networked power controller.

The RPM1521 is controlled via an HTTP CGI endpoint using HTTP basic auth::

    curl --user user:pwd \\
        "http://192.168.1.100/nagios_powerctrl.csp?slave_id=1&port=<PORT>&ctrl_kind=<KIND>"

where ``ctrl_kind=1`` turns the outlet on and ``ctrl_kind=2`` turns it off.

The outlet state is read back from a separate status CGI::

    curl --user user:pwd "http://192.168.1.100/nagios_power_status.csp"

which returns a list whose second to last element holds the on/off state of each
outlet (0 = off, 1 = on).

    NetworkPowerPort:
        model: rpm1521
        host: 'http://admin:secret@192.168.1.10'
        index: 1
"""

import json

import requests

SLAVE_ID = 1
CTRL_KIND_ON = 1
CTRL_KIND_OFF = 2


def power_set(host, port, index, value):
    index = int(index)
    ctrl_kind = CTRL_KIND_ON if value else CTRL_KIND_OFF
    params = {
        "slave_id": SLAVE_ID,
        "port": index,
        "ctrl_kind": ctrl_kind,
    }
    r = requests.get(f"{host}/nagios_powerctrl.csp", params=params)
    r.raise_for_status()


def power_get(host, port, index):
    index = int(index)
    params = {
        "slave_id": SLAVE_ID,
    }
    r = requests.get(f"{host}/nagios_power_status.csp", params=params)
    r.raise_for_status()

    # The status CGI returns a list literal, e.g.
    #   ['RPM1521E','0.0','NULL','1','1','109.9',['1','0'],['0','1'],['0.0','0.0']]
    # It contains several bracketed sub-lists; the second to last one holds the
    # on/off status of each outlet.
    data = json.loads(r.text.replace("'", '"'))
    socket_states = data[-2]
    return int(socket_states[index - 1]) == 1
