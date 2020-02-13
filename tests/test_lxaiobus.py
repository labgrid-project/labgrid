import pytest
import requests

from labgrid.resource import LXAIOBusPIO
from labgrid.driver import LXAIOBusPIODriver

@pytest.fixture(scope='function')
def mock_server(mocker):
    def get(url):
        r = mocker.MagicMock()
        if url.endswith("/nodes/"):
            r.json.return_value = {"code": 0, "result": ["IOMux-5a6ecbea"]}
        if "/pins/" in url:
            r.json.return_value = {"code": 0, "result": 1}
        return r
    def post(url, data=None):
        r = mocker.MagicMock()
        if "/pins/" in url:
            r.json.return_value = {"code": 0, "result": None}
        return r
    mock_get = mocker.patch('requests.get')
    mock_get.side_effect = get
    mock_post = mocker.patch('requests.post')
    mock_post.side_effect = post
    return (mock_get, mock_post)


@pytest.fixture(scope='function')
def lxa_pin(mock_server, target):
    r = LXAIOBusPIO(target, name=None, host='localhost:8080', node='IOMux-5a6ecbea', pin='OUT0')
    return r


@pytest.fixture(scope='function')
def lxa_driver(mock_server, target, lxa_pin):
    mock_get, mock_post = mock_server

    s = LXAIOBusPIODriver(target, name=None)
    target.activate(s)
    mock_get.assert_called_with('http://localhost:8080/nodes/')
    return s


def test_lxa_resource_instance(mock_server, lxa_pin):
    assert (isinstance(lxa_pin, LXAIOBusPIO))


def test_lxa_driver_instance(mock_server, lxa_driver):
    assert isinstance(lxa_driver, LXAIOBusPIODriver)


def test_lxa_set(mock_server, lxa_driver):
    mock_get, mock_post = mock_server

    lxa_driver.set(True)
    mock_post.assert_called_once_with('http://localhost:8080/nodes/IOMux-5a6ecbea/pins/OUT0/', data={"value": "1"})


def test_lxa_unset(mock_server, lxa_driver):
    mock_get, mock_post = mock_server

    lxa_driver.set(False)
    mock_post.assert_called_once_with('http://localhost:8080/nodes/IOMux-5a6ecbea/pins/OUT0/', data={"value": "0"})


def test_lxa_get(mock_server, lxa_driver):
    mock_get, mock_post = mock_server
    val = lxa_driver.get()
    mock_get.assert_called_with('http://localhost:8080/nodes/IOMux-5a6ecbea/pins/OUT0/')
    assert val == True
