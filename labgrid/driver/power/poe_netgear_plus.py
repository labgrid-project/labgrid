"""Control NETGEAR Plus devices via HTTP.

Available switch models:
https://github.com/foxey/py-netgear-plus?tab=readme-ov-file#supported-and-tested-netgear-modelsproducts-and-firmware-versions

The password defaults to "P4ssword", but can be configured on a per-device basis like this:

NetworkPowerPort:
  model: poe_netgear_plus
  host: 'http://username_is_unused:AnotherP4ssword@192.168.0.239/'
  index: 7

Omitting the password defaults as described above.

NetworkPowerPort:
  model: poe_netgear_plus
  host: 'http://192.168.0.239/'
  index: 7

"""

from urllib.parse import urlparse

from py_netgear_plus import NetgearSwitchConnector

from ..exception import ExecutionError


def _get_hostname_and_password(url: str) -> tuple[str, str]:
    """Obtain credentials from url or default and return hostname and password.

    If no password is in the URL return "P4ssword", which fulfills  the minimal requirements from Netgear:
    - 8-20 characters
    - at least one upper case character
    - at least one lower case character
    - at least one number

    Args:
        url: A URL with an optional basic auth prefix.

    Returns:
        A tuple of the hostname, and the extracted or default password

    """
    parse_result = urlparse(url)
    if parse_result.scheme != "http":
        raise ExecutionError(f"URL must start with http://, found {parse_result.scheme} for {url}.")

    password = "P4ssword" if parse_result.password is None else parse_result.password

    return parse_result.hostname, password


def power_set(host: str, _port: int, index: int, value: bool) -> None:
    """Set the PoE output index based for a given host.

    Args:
        host: The netloc with optional password e.g. "192.168.0.239" or ":P4ssword@192.168.0.239"
        _port: As the webserver of the switch is always on port 80, this is ignored
        index: Zero based access to the switches network ports
        value: Whether the port should enable PoE output

    """
    index = int(index)
    netgear_port_number = index + 1

    (hostname, password) = _get_hostname_and_password(host)

    sw = NetgearSwitchConnector(hostname, password)
    sw.autodetect_model()
    try:
        sw.get_login_cookie()
        sw._get_switch_metadata()
        if value:
            sw.turn_on_poe_port(netgear_port_number)
        else:
            sw.turn_off_poe_port(netgear_port_number)
    finally:
        sw.delete_login_cookie()


def power_get(host: str, _port: int, index: int) -> bool:
    """Determine whether a given Port has PoE enabled.

    Args:
        host: The netloc with optional password e.g. "192.168.0.239" or ":P4ssword@192.168.0.239"
        _port: As the webserver of the switch is always on port 80, this is ignored
        index: Zero based access to the switches network ports

    Returns:
        Whether the PoE output is enabled.

    Raises:
        ExecutionError: In case the status dictionary contains unexpected PoE status values.

    """
    index = int(index)
    netgear_port_number = index + 1

    (hostname, password) = _get_hostname_and_password(host)

    sw = NetgearSwitchConnector(hostname, password)
    sw.autodetect_model()
    try:
        sw.get_login_cookie()
        sw._get_switch_metadata()
        data = sw._get_poe_port_config()
        key = f"port_{netgear_port_number}_poe_power_active"
        if data[key] == "on":
            return True
        if data[key] == "off":
            return False
        msg = f"Expected literal 'on'|'off', found {data[key]}"
        raise ExecutionError(msg)
    finally:
        sw.delete_login_cookie()
