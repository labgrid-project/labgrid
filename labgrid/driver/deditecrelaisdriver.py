# pylint: disable=no-member
import subprocess
import attr

from .common import Driver
from ..factory import target_factory
from ..resource.udev import DeditecRelais8
from ..step import step
from ..protocol import DigitalOutputProtocol
from ..util.agentwrapper import AgentWrapper


@target_factory.reg_driver
@attr.s(cmp=False)
class DeditecRelaisDriver(Driver, DigitalOutputProtocol):
    bindings = {
        "relais": {DeditecRelais8},
    }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.wrapper = None

    def on_activate(self):
        self.wrapper = AgentWrapper(None)
        self.proxy = self.wrapper.load('deditec_relais8')

    def on_deactivate(self):
        self.wrapper.close()
        self.wrapper = None
        self.proxy = None

    @Driver.check_active
    @step(args=['status'])
    def set(self, status):
        self.proxy.set(self.relais.busnum, self.relais.devnum, self.relais.index, status)

    @Driver.check_active
    @step(result=True)
    def get(self):
        return self.proxy.get(self.relais.busnum, self.relais.devnum, self.relais.index)
