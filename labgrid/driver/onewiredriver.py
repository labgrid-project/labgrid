import logging

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
        import onewire
        super().__attrs_post_init__()
        self.onewire = onewire.Onewire(self.port.host)

    def set(self, status):
        if status == True:
            self.onewire.set(self.port.path, '1')
        else:
            self.onewire.set(self.port.path, '0')

    def get(self):
        status = self.onewire.get(self.port.path)
        return status == '1'
