import attr

from .common import Driver
from ..factory import target_factory
from ..resource.remote import NetworkHIDRelay
from ..step import step
from ..protocol import DigitalOutputProtocol
from ..util.agentwrapper import AgentWrapper


@target_factory.reg_driver
@attr.s(eq=False)
class HIDRelayDriver(Driver, DigitalOutputProtocol):
    bindings = {
        "relay": {"HIDRelay", NetworkHIDRelay},
    }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.wrapper = None

    def on_activate(self):
        if isinstance(self.relay, NetworkHIDRelay):
            host = self.relay.host
        else:
            host = None
        self.wrapper = AgentWrapper(host)
        self.proxy = self.wrapper.load('usb_hid_relay')

    def on_deactivate(self):
        self.wrapper.close()
        self.wrapper = None
        self.proxy = None

    @Driver.check_active
    @step(args=['status'])
    def set(self, status):
        if self.relay.invert:
            status = not status
        self.proxy.set(self.relay.busnum, self.relay.devnum, self.relay.index, status)

    @Driver.check_active
    @step(result=True)
    def get(self):
        status = self.proxy.get(self.relay.busnum, self.relay.devnum, self.relay.index)
        if self.relay.invert:
            status = not status
        return status
