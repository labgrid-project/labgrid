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
        self._consts = import_module('pyModbusTCP.constants')
        self.client = None

    def on_activate(self):
        # we can only forward if the backend knows which port to use
        host, port = proxymanager.get_host_and_port(self.coil, default_port=502)
        self.client = self._module.ModbusClient(
            host=host, port=int(port), auto_open=True, auto_close=True)

    def on_deactivate(self):
        self.client = None

    def _handle_error(self, action):
        error_code = self.client.last_error
        if error_code == self._consts.MB_EXCEPT_ERR:
            exc = self.client.last_except
            if exc not in [self._consts.EXP_ACKNOWLEDGE, self._consts.EXP_NONE]:
                raise ExecutionError(
                    f'Could not {action} coil (code={error_code}/exception={exc})')
        raise ExecutionError(f'Could not {action} coil (code={error_code})')

    @Driver.check_active
    def set(self, status):
        write_status = None
        if self.coil.invert:
            status = not status
        if self.coil.write_multiple_coils:
            write_status = self.client.write_multiple_coils(
                self.coil.coil, [bool(status)]
            )
        else:
            write_status = self.client.write_single_coil(self.coil.coil, bool(status))
        if write_status is None:
            self._handle_error("write")

    @Driver.check_active
    def get(self):
        status = self.client.read_coils(self.coil.coil)
        if status is None:
            self._handle_error("read")

        status = status[0]
        if self.coil.invert:
            status = not status
        return status
