'''
Driver for Digital Loggers PDU that use the legacy HTTP API.
Tested with Web Power Switch 7.
'''

import re
import requests

def power_set(host, port, index, value):
    assert port is None

    index = int(index)
    value = 'ON' if value else 'OFF'
    host = f'{host}/outlet?{index}={value}'
    r = requests.get(host)
    r.raise_for_status()

def power_get(host, port, index):
    assert port is None

    index = int(index)
    host = f'{host}/status'
    r = requests.get(host)
    r.raise_for_status()

    # Basically, an HTML page is returned, whose body contents are like:
    # <div id="state">ff</div><div id="lock">00</div><div id="perm">ff</div>
    # We're interested in the value of state div - 'ff' above. And the
    # status is basically the corresponding outlet bit index. So, outlet
    # 1 is the 0th bit, with 1 for ON and 0 for OFF.
    statuses = re.findall(r'state">(\w+)<', r.text)[0]
    return bool(int(statuses, 16) & (1 << (index - 1)))
