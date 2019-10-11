"""All GPIO-related drivers"""
import attr

from ..factory import target_factory
from ..protocol import DigitalOutputProtocol
from ..resource.remote import NetworkSysfsGPIO
from ..step import step
from .common import Driver
from ..util.agentwrapper import AgentWrapper


@target_factory.reg_driver
@attr.s(eq=False)
class GpioDigitalOutputDriver(Driver, DigitalOutputProtocol):

    bindings = {
        "gpio": {"SysfsGPIO", "NetworkSysfsGPIO"},
    }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.wrapper = None

    def on_activate(self):
        if isinstance(self.gpio, NetworkSysfsGPIO):
            host = self.gpio.host
        else:
            host = None
        self.wrapper = AgentWrapper(host)
        self.proxy = self.wrapper.load('sysfsgpio')

    def on_deactivate(self):
        self.wrapper.close()
        self.wrapper = None
        self.proxy = None

    @Driver.check_active
    @step(args=['status'])
    def set(self, status):
        self.proxy.set(self.gpio.index, status)

    @Driver.check_active
    @step(result=True)
    def get(self):
        return self.proxy.get(self.gpio.index)
