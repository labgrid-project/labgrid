#!/usr/bin/env python3

import time

import attr

from .common import Driver
from ..factory import target_factory
from ..protocol import PowerProtocol
from ..step import step
from ..util import Timeout


class MQTTError(Exception):
    pass

@target_factory.reg_driver
@attr.s(eq=False)
class TasmotaPowerDriver(Driver, PowerProtocol):
    bindings = {
            "power": {"TasmotaPowerPort"}
    }
    delay = attr.ib(default=2.0, validator=attr.validators.instance_of(float))
    _client = attr.ib(default=None)
    _status = attr.ib(default=None)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        import paho.mqtt.client as mqtt
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    def on_activate(self):
        self._client.on_message = self._on_message
        self._client.on_connect = self._on_connect
        self._client.connect(self.power.host)
        self._client.loop_start()

    def on_deactivate(self):
        self._client.loop_stop()

    def _on_message(self, client, userdata, msg):
        if msg.payload == b'ON':
            status = True
        elif msg.payload == b'OFF':
            status = False
        else:
            raise ValueError(f"Unknown status: {msg.payload}. Must be 'ON' or 'OFF'")
        self._status = status

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        client.subscribe(self.power.status_topic)

    def _publish(self, topic, payload):
        msg = self._client.publish(topic, payload=payload)
        timeout = Timeout(3.0)
        while not msg.is_published:
            time.sleep(0.1)
            if timeout.expired:
                raise MQTTError("publish timed out")
        return msg

    @Driver.check_active
    @step()
    def on(self):
        self._publish(self.power.power_topic, "ON")
        timeout = Timeout(3.0)
        while self._status is False:
            time.sleep(0.1)
            if timeout.expired:
                raise MQTTError("Port did not change status within 3 seconds")

    @Driver.check_active
    @step()
    def off(self):
        self._publish(self.power.power_topic, "OFF")
        timeout = Timeout(3.0)
        while self._status is True:
            time.sleep(0.1)
            if timeout.expired:
                raise MQTTError("Port did not change status within 3 seconds")

    @Driver.check_active
    @step()
    def cycle(self):
        self.off()
        time.sleep(self.delay)
        self.on()

    @Driver.check_active
    @step()
    def get(self):
        self._client.publish(self.power.power_topic)
        timeout = Timeout(3.0)
        while self._status is None:
            time.sleep(0.1)
            if timeout.expired:
                raise MQTTError("Could not get initial status")
        return self._status
