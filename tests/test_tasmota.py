from labgrid.resource.mqtt import TasmotaPowerPort
from labgrid.driver.mqtt import TasmotaPowerDriver

import pytest

pytest.importorskip("paho.mqtt.client")


def test_tasmota_resource(target, mocker):
    mocker.patch("paho.mqtt.client.Client.connect", return_value=None)
    mocker.patch("paho.mqtt.client.Client.loop_start", return_value=None)
    pw_set = mocker.patch("paho.mqtt.client.Client.username_pw_set", return_value=None)
    TasmotaPowerPort(target, name=None, host="localhost", avail_topic="test", power_topic="test", status_topic="test")
    pw_set.assert_called_once_with(None, None)


def test_tasmota_driver(target, mocker):
    mocker.patch("paho.mqtt.client.Client.connect", return_value=None)
    mocker.patch("paho.mqtt.client.Client.loop_start", return_value=None)
    pw_set = mocker.patch("paho.mqtt.client.Client.username_pw_set", return_value=None)
    res = TasmotaPowerPort(
        target,
        name=None,
        host="localhost",
        avail_topic="test",
        power_topic="test",
        status_topic="test",
        username="foo",
        password="bar",
    )
    res.manager._available.add("test")
    driver = TasmotaPowerDriver(target, name=None)
    target.activate(driver)
    pw_set.assert_called_once_with("foo", "bar")
