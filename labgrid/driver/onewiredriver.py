import attr

from ..factory import target_factory
from ..resource import OneWirePIO
from ..protocol import DigitalOutputProtocol
from .common import Driver

@target_factory.reg_driver
@attr.s(cmp=False)
class OneWirePIODriver(Driver, DigitalOutputProtocol):

    bindings = {"port": OneWirePIO, }

    def __attrs_post_init__(self):
        import onewire
        super().__attrs_post_init__()
        self.onewire = onewire.Onewire(self.port.host)

    @Driver.check_active
    def set(self, status):
        if self.port.invert:
            status = not status
        if status == True:
            self.onewire.set(self.port.path, '1')
        else:
            self.onewire.set(self.port.path, '0')

    @Driver.check_active
    def get(self):
        status = self.onewire.get(self.port.path)
        if self.port.invert:
            status = not status
        return status == '1'
