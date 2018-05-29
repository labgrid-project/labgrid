import sys

from ..exception import ExecutionError

import requests

# This driver implements a power port for Gude Power Switches with up to
# 24 ports.
# These switches differ in their API to the previous 8-port switches for set-
# and get-commands.
#
# Driver has been tested with:
# * Gude Expert Power Control 8080

def power_set(host, index, value):
    # The gude web-interface uses different pages for the three groups of
    # switches. The web-interface always uses the 'correct' page to set a
    # value. But commands for all pages are accepted on all pages.
    index = int(index)
    assert 1 <= index <= 24
    # access the web interface...
    value = 1 if value else 0
    r = requests.get(
        "http://{}/ov.html?cmd=1&p={}&s={}".format(host, index, value)
    )
    r.raise_for_status()


def power_get(host, index):
    # The status of the ports is made available via a html <meta>-tag using the
    # following format:
    # <meta http-equiv="powerstate" content="Power Port 1,0">
    # Again the status of all ports is made available on all pages.
    index = int(index)
    assert 1 <= index <= 24
    # get the contents of the main page
    r = requests.get("http://{}/ov.html".format(host))
    r.raise_for_status()
    for line in r.text.splitlines():
        if line.find("content=\"Power Port {}".format(index)) > 0:
            if line.find(",0") > 0:
                return False
            elif line.find(",1") > 0:
                return True
            else:
                raise ExecutionError("failed to parse the port status")
    # if we got this far, something is wrong with the website
    raise ExecutionError("failed to find the port")
