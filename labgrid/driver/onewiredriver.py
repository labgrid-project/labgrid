from importlib import import_module
import attr

from ..exceptions import InvalidConfigError
from ..factory import target_factory
from ..protocol import DigitalOutputProtocol
from ..util.proxy import proxymanager
from .common import Driver
from .exception import ExecutionError
from ..step import step

@target_factory.reg_driver
@attr.s(eq=False)
class OneWirePIODriver(Driver, DigitalOutputProtocol):

    bindings = {"port": "OneWirePIO", }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._module = import_module('onewire')
        self._onewire = None
        if "PIO" not in self.port.path:
            raise InvalidConfigError(
                f"Invalid OneWire path {self.port.path} (needs to be in the form of ??.????????????/PIO.?)"  # pylint: disable=line-too-long
            )

    def on_activate(self):
        # we can only forward if the backend knows which port to use
        host, port = proxymanager.get_host_and_port(self.port)
        self._onewire = self._module.Onewire(
            f"{host}:{port}"
        )

    def on_deactivate(self):
        self._onewire = None

    @Driver.check_active
    @step(args=['status'])
    def set(self, status):
        if self.port.invert:
            status = not status
        if status:
            self._onewire.set(self.port.path, '1')
        else:
            self._onewire.set(self.port.path, '0')

    @Driver.check_active
    @step(result=['True'])
    def get(self):
        path = self.port.path.replace("PIO", "sensed")
        status = self._onewire.get(path)
        if status is None:
            raise ExecutionError(f"Failed to get OneWire value for {path}")
        if status not in ['0', '1']:
            raise ExecutionError(f"Invalid OneWire value ({repr(status)})")
        status = (status == '1')
        if self.port.invert:
            status = not status
        return status
