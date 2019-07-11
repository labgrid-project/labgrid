from importlib import import_module
import attr

from ..exceptions import InvalidConfigError
from ..factory import target_factory
from ..resource import OneWirePIO
from ..protocol import DigitalOutputProtocol
from ..util.proxy import proxymanager
from .common import Driver
from .exception import ExecutionError
from ..step import step

@target_factory.reg_driver
@attr.s(cmp=False)
class OneWirePIODriver(Driver, DigitalOutputProtocol):

    bindings = {"port": OneWirePIO, }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._module = import_module('onewire')
        self._onewire = None
        if "PIO" not in self.port.path:
            raise InvalidConfigError(
                    "Invalid OneWire path {} (needs to be in the form of ??.????????????/PIO.?)"
                    .format(self.port.path))

    def on_activate(self):
        # we can only forward if the backend knows which port to use
        host, port = proxymanager.get_host_and_port(self.port)
        self._onewire = self._module.Onewire(
            "{}:{}".format(host, port)
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
            raise ExecutionError("Failed to get OneWire value for {}".format(path))
        if status not in ['0', '1']:
            raise ExecutionError("Invalid OneWire value ({})".format(repr(status)))
        status = True if status == '1' else False
        if self.port.invert:
            status = not status
        return status
