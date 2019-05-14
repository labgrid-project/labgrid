import attr

from ..factory import target_factory
from ..resource import OneWirePIO
from ..protocol import DigitalOutputProtocol
from ..util.proxy import proxymanager
from .common import Driver

@target_factory.reg_driver
@attr.s(cmp=False)
class OneWirePIODriver(Driver, DigitalOutputProtocol):

    bindings = {"port": OneWirePIO, }

    def __attrs_post_init__(self):
        import onewire
        super().__attrs_post_init__()
        self._onewire = None
        self._host = None
        self._port = None

    def on_activate(self):
        import onewire
        # we can only forward if the backend knows which port to use
        self._host, self._port = proxymanager.get_host_and_port(self.port)
        self._onewire = onewire.Onewire(
            "{}:{}".format(self._host, self._port)
        )

    def on_deactivate(self):
        self._onewire = None

    @Driver.check_active
    def set(self, status):
        if self.port.invert:
            status = not status
        if status:
            self._onewire.set(self.port.path, '1')
        else:
            self._onewire.set(self.port.path, '0')

    @Driver.check_active
    def get(self):
        status = self._onewire.get(self.port.path)
        if self.port.invert:
            status = not status
        return status == '1'
