import logging
import requests

import attr

from ..factory import target_factory
from ..resource import OneWirePIO
from ..protocol import DigitalOutputProtocol
from .common import Driver

@target_factory.reg_driver
@attr.s
class OneWirePIODriver(Driver, DigitalOutputProtocol):

    bindings = {"port": OneWirePIO, }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    def set(self, status):
        if status == True:
            payload = { self.port.portname: ["on", 'CHANGE']}
            r = requests.get(self.port.url, params=payload, stream=True)
            print(r.url)
            if r.status_code != 200:
                raise Exception
        else:
            payload = { self.port.portname: "CHANGE"}
            r = requests.get(self.port.url, params=payload, stream=True)
            print(r.url)
            if r.status_code != 200:
                raise Exception

    def get(self):
        pass
