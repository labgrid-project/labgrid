from importlib import import_module
import attr

from ..factory import target_factory
from ..protocol import DigitalOutputProtocol
from ..util.proxy import proxymanager
from .common import Driver
from .exception import ExecutionError

@target_factory.reg_driver
@attr.s(eq=False)
class ModbusCoilDriver(Driver, DigitalOutputProtocol):
    bindings = {"coil": "ModbusTCPCoil", }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._module = import_module('pyModbusTCP.client')
        self.client = None

    def on_activate(self):
        # we can only forward if the backend knows which port to use
        host, port = proxymanager.get_host_and_port(self.coil, default_port=502)
        self.client = self._module.ModbusClient(
            host=host, port=int(port), auto_open=True, auto_close=True)

    def on_deactivate(self):
        self.client = None

    @Driver.check_active
    def set(self, status):
        if self.coil.invert:
            status = not status
        write_status = self.client.write_single_coil(self.coil.coil, bool(status))
        if write_status is None:
            error_code = self.client.last_error()
            raise ExecutionError('Could not write coil (code={})'.format(error_code))

    @Driver.check_active
    def get(self):
        status = self.client.read_coils(self.coil.coil)
        if status is None:
            error_code = self.client.last_error()
            raise ExecutionError('Could not read coil (code={})'.format(error_code))

        status = status[0]
        if self.coil.invert:
            status = not status
        return status
