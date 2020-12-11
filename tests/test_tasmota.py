from labgrid.resource.mqtt import TasmotaPowerPort
from labgrid.driver.mqtt import TasmotaPowerDriver

import pytest

pytest.importorskip("paho.mqtt.client")


def test_tasmota_resource(target, mocker):
    mocker.patch('paho.mqtt.client.Client.connect', return_value=None)
    mocker.patch('paho.mqtt.client.Client.loop_start', return_value=None)
    TasmotaPowerPort(target, name=None, host="localhost", avail_topic="test",
                     power_topic="test", status_topic="test")


def test_tasmota_driver(target, mocker):
    mocker.patch('paho.mqtt.client.Client.connect', return_value=None)
    mocker.patch('paho.mqtt.client.Client.loop_start', return_value=None)
    res = TasmotaPowerPort(target, name=None, host="localhost", avail_topic="test",
                           power_topic="test", status_topic="test")
    res.manager._available.add("test")
    driver = TasmotaPowerDriver(target, name=None)
    target.activate(driver)
