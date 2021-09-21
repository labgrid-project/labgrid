import requests

from ..exception import ExecutionError


# This driver implements a power port for Gude EPC-8316 Power Switches.
# These switches differ in their API to the previous switches for
# get-commands (because of a firmware bug).
#
# Apart from a workaround for this bug and reduced port index limits of
# 8 instead of 24, this implementation works just like gude24.py.
#
# Driver has been tested with:
# * Gude Expert Power Control 8316 (firmware v1.2.0)

PORT = 80

def power_set(host, port, index, value):
    # The gude web-interface uses different pages for the three groups of
    # switches. The web-interface always uses the 'correct' page to set a
    # value. But commands for all pages are accepted on all pages.
    index = int(index)
    assert 1 <= index <= 8
    # access the web interface...
    value = 1 if value else 0
    r = requests.get(
        f"http://{host}:{port}/ov.html?cmd=1&p={index}&s={value}"
    )
    r.raise_for_status()


def power_get(host, port, index):
    # The status of the ports is made available via a html <meta>-tag using the
    # following format:
    # <meta http-equiv="powerstate" content="Power Port ,0">
    #
    # The index of each port should normally be in there, but isn't, because of
    # a firmware bug:
    # <meta http-equiv="powerstate" content="Power Port 1,0">
    #
    # Again the status of all ports is made available on all pages.
    index = int(index)
    assert 1 <= index <= 8
    # get the contents of the main page
    r = requests.get(f"http://{host}:{port}/ov.html")
    r.raise_for_status()
    for line_no, line in enumerate(r.text.splitlines()):
        if line_no == index and line.find("content=\"Power Port ") > 0:
            if line.find(",0") > 0:
                return False
            if line.find(",1") > 0:
                return True

            raise ExecutionError("failed to parse the port status")
    # if we got this far, something is wrong with the website
    raise ExecutionError("failed to find the port")
