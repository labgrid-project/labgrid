import requests
import re

from labgrid.driver.exception import ExecutionError


# This driver implements a power port for Aviosys Power Switches.
# Aviosys HTTP web-interface is described here https://www.aviosys.com/products/lib/httpapi.html
# The command format is http://ip:port/set.cmd?user=account+pass=password+cmd=command

# The powerdriver.py uses the 'PORT' variable => backend_port = getattr(self.backend, 'PORT', None)
PORT = 80
USER = "admin"
PASS = 12345678
NUMBER_OF_OUTLETS = 4

def power_set(host, port, index, value):
    # <!--CGI-DATABEG-->
    # <p>
    # p61=1</p>
    # <!--CGI-DATAEND-->
    index = int(index)
    assert 1 <= index <= NUMBER_OF_OUTLETS
    value = 1 if value else 0

    r = requests.get(
        f"http://{host}:{port}/set.cmd?user={USER}+pass={PASS}+cmd=setpower+p6{index}={value}"
    )
    r.raise_for_status()

def power_get(host, port, index):
    # <!--CGI-DATABEG-->
    # <p>
    # p61=1,p62=0,p63=0,p64=0
    # </p>
    # <!--CGI-DATAEND-->
    index = int(index)
    assert 1 <= index <= NUMBER_OF_OUTLETS

    r = requests.get(
        f"http://{host}:{port}/set.cmd?user={USER}+pass={PASS}+cmd=getpower+p6{index}=0"
    )
    r.raise_for_status()

    data = r.text
    matches = re.findall(r'p6(\d)=(\d)', data)
    values = {f"p6{index}": int(value) for index, value in matches}

    state = values[f"p6{index}"]
    return bool(int(state))
