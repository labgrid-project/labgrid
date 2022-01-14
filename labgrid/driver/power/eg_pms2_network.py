import re
import requests

from ..exception import ExecutionError

# This driver implementes a power port for the EG_PMS2_LAN & EG_PMS2_WLAN
# devices, it works through a simple HTTP interface, that requires a login.
# Driver has been tested with:
# * EG_PMS2_LAN

# The default HTTP port for usage via the SSH proxy.
PORT = 80

# The login was successful when we can locate a Log out button
LOGIN_SUCCESS_REGEX = r'<div class="boxmenuitem"><a href="login\.html">Log Out</a></div>'
# Search for a string similar to: "var sockstates = [1,1,1,1];" and create
# a match group out of the numbers within the square brackets.
SOCKSTATES_REGEX = r"var\s+sockstates\s+=\s+\[([01]),([01]),([01]),([01])\];"


def login(base_url: str) -> None:
    """
    Use the default password 1, because labgrid doesn't support password
    encryption, modifying the password doesn't secure the device as the
    password would be stored as plain-text.
    """
    login_url = f"{base_url}/login.html"
    try:
        response = requests.post(login_url, data={'pw': 1})
    except requests.exceptions.ConnectionError as err:
        raise ExecutionError(
            f"Device not found at {base_url} or the network interface of the "
            "device is not active (press the reset button on the device)"
        ) from err
    if response.status_code != 200 or not re.search(LOGIN_SUCCESS_REGEX,
                                                    response.text):
        raise ExecutionError("Login to Energenie web interface failed")


def logout(base_url: str) -> None:
    """
    After a successful login, the session is reserved for the IP address.
    Logout explicitly to allow accessing the device from different hosts.
    """
    response = requests.get(f"{base_url}/login.html")
    if response.status_code != 200:
        raise ExecutionError("Logout from Energenie web interface failed")


def power_set(host, port, index, value):
    base_url = f"http://{host}:{port}"
    index = int(index)
    assert 1 <= index <= 4

    value = 1 if value else 0
    login(base_url=base_url)
    response = requests.post(base_url, data={f'cte{index}': value})
    response.raise_for_status()
    logout(base_url=base_url)
    if not response.status_code == 200:
        raise ExecutionError(f"Switching socket at index {index} "
                             f"{'on' if value else 'off'} failed")


def power_get(host, port, index):
    base_url = f"http://{host}:{port}"
    index = int(index)
    assert 1 <= index <= 4

    # Fetch status
    login(base_url=base_url)
    response = requests.get(f"{base_url}/energenie.html")
    response.raise_for_status()
    logout(base_url=base_url)
    match_group = re.search(SOCKSTATES_REGEX, response.text)
    sockstates = [int(match_group.group(x)) for x in range(1, 5)]
    return sockstates[index - 1] == 1
