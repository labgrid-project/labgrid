import pytest
import requests

from labgrid.driver import HttpDigitalOutputDriver
from labgrid.resource import HttpDigitalOutput


@pytest.fixture(scope="function")
def mock_server(mocker):
    state = '"Unknown"'

    def request(method, url, data=None):
        nonlocal state
        state = data
        return mocker.MagicMock()

    def get(url):
        r = mocker.MagicMock()
        r.text = state
        return r

    mock_request = mocker.patch("requests.request")
    mock_request.side_effect = request
    mock_get = mocker.patch("requests.get")
    mock_get.side_effect = get

    return (mock_request, mock_get)


def _make_http_driver(target, with_tls, with_regex, separate_get, match_error):
    scheme = "https" if with_tls else "http"
    url = f"{scheme}://host.example/set"
    url_get = f"{scheme}://host.example/get" if separate_get else ""

    body_get_asserted = ".*n.*" if with_regex else ""
    body_get_deasserted = ".*ff.*" if with_regex else ""

    if match_error:
        body_get_asserted = "--- DOES NOT MATCH ---"
        body_get_deasserted = "--- DOES NOT MATCH EITHER ---"

    dig_out_res = HttpDigitalOutput(
        target,
        name=None,
        url=url,
        body_asserted='"On"',
        body_deasserted='"Off"',
        method="PUT",
        url_get=url_get,
        body_get_asserted=body_get_asserted,
        body_get_deasserted=body_get_deasserted,
    )

    http_driver = HttpDigitalOutputDriver(target, name=None)
    target.activate(http_driver)

    return http_driver


@pytest.mark.parametrize(
    "asserted,with_tls,with_regex,separate_get",
    [
        (False, False, False, False),
        (True, False, False, False),
        (True, True, False, False),
        (True, False, True, False),
        (False, False, True, False),
        (True, False, False, True),
        (True, True, True, True),
    ],
)
def test_set_get(asserted, with_tls, with_regex, separate_get, target, mock_server):
    http_driver = _make_http_driver(target, with_tls, with_regex, separate_get, False)
    mock_request, mock_get = mock_server

    data = '"On"' if asserted else '"Off"'
    scheme = "https" if with_tls else "http"
    port = 443 if with_tls else 80
    get_endpoint = "get" if separate_get else "set"

    set_url = f"{scheme}://host.example:{port}/set"
    get_url = f"{scheme}://host.example:{port}/{get_endpoint}"

    http_driver.set(asserted)
    mock_request.assert_called_once_with("PUT", set_url, data=data)

    assert http_driver.get() == asserted
    mock_get.assert_called_once_with(get_url)


def test_match_exception(target, mock_server):
    http_driver = _make_http_driver(target, False, False, False, True)
    mock_request, mock_get = mock_server

    http_driver.set(True)
    with pytest.raises(Exception):
        http_driver.get()
