from importlib import import_module

import attr

from ..factory import target_factory
from ..resource import ModbusTCPCoil
from ..protocol import DigitalOutputProtocol
from .common import Driver

@target_factory.reg_driver
@attr.s(cmp=False)
class ModbusCoilDriver(Driver, DigitalOutputProtocol):
    bindings = {"coil": ModbusTCPCoil, }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._module = import_module('pyModbusTCP.client')
        port = "502"
        host = self.coil.host
        if ':' in host:
            host, port = host.split(':', 1)
        self.client = self._module.ModbusClient(host=host,
                port=int(port), auto_open=True, auto_close=True)

    @Driver.check_active
    def set(self, status):
        if self.coil.invert:
            status = not status
        self.client.write_single_coil(self.coil.coil, bool(status))

    @Driver.check_active
    def get(self):
        status = self.client.read_coils(self.coil.coil)
        assert len(status) == 1
        status = status[0]
        if self.coil.invert:
            status = not status
        return status
