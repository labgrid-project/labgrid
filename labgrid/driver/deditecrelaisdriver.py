import attr

from .common import Driver
from ..factory import target_factory
from ..resource.remote import NetworkDeditecRelais8
from ..step import step
from ..protocol import DigitalOutputProtocol
from ..util.agentwrapper import AgentWrapper


@target_factory.reg_driver
@attr.s(eq=False)
class DeditecRelaisDriver(Driver, DigitalOutputProtocol):
    bindings = {
        "relais": {"DeditecRelais8", NetworkDeditecRelais8},
    }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.wrapper = None

    def on_activate(self):
        if isinstance(self.relais, NetworkDeditecRelais8):
            host = self.relais.host
        else:
            host = None
        self.wrapper = AgentWrapper(host)
        self.proxy = self.wrapper.load('deditec_relais8')

    def on_deactivate(self):
        self.wrapper.close()
        self.wrapper = None
        self.proxy = None

    @Driver.check_active
    @step(args=['status'])
    def set(self, status):
        if self.relais.invert:
            status = not status
        self.proxy.set(self.relais.busnum, self.relais.devnum, self.relais.index, status)

    @Driver.check_active
    @step(result=True)
    def get(self):
        status = self.proxy.get(self.relais.busnum, self.relais.devnum, self.relais.index)
        if self.relais.invert:
            status = not status
        return status
