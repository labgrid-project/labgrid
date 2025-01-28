import attr

from .common import Driver
from ..factory import target_factory
from ..step import step
from ..protocol import DigitalOutputProtocol
from ..util.agentwrapper import AgentWrapper
from ..resource.remote import NetworkKMTronicRelay


@target_factory.reg_driver
@attr.s(eq=False)
class KMTronicRelayDriver(Driver, DigitalOutputProtocol):
    bindings = {
        "relay": {"KMTronicRelay", "NetworkKMTronicRelay"},
    }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.wrapper = None

    def on_activate(self):
        if isinstance(self.relay, NetworkKMTronicRelay):
            host = self.relay.host
        else:
            host = None
        self.wrapper = AgentWrapper(host)
        self.proxy = self.wrapper.load('kmtronic_relay')

    def on_deactivate(self):
        self.wrapper.close()
        self.wrapper = None
        self.proxy = None

    @Driver.check_active
    @step(args=['status'])
    def set(self, status):
        self.proxy.set(self.relay.path, self.relay.index, status)

    @Driver.check_active
    @step(result=True)
    def get(self):
        status = self.proxy.get(self.relay.path, self.relay.index, self.relay.ports)
        return status
