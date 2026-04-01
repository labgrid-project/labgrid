"""Descriptor based GPIO-related drive"""
import attr

from ..factory import target_factory
from ..protocol import DigitalOutputProtocol
from ..step import step
from .common import Driver
from ..util.agentwrapper import AgentWrapper
from ..resource.remote import NetworkGpiodGPIO
from ..resource.base import GpiodGPIO

@target_factory.reg_driver
@attr.s(eq=False)
class GpiodDigitalOutputDriver(Driver, DigitalOutputProtocol):
    bindings = {
        "gpio": { "GpiodGPIO", "NetworkGpiodGPIO"},
    }
    initval = attr.ib(default=None, validator=attr.validators.optional(attr.validators.instance_of(bool)))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.wrapper = None

    def on_activate(self):
        if isinstance(self.gpio, NetworkGpiodGPIO):
            host = self.gpio.host
        else:
            host = None
        self.wrapper = AgentWrapper(host)
        self.proxy = self.wrapper.load('gpiodgpio')

    def on_deactivate(self):
        self.wrapper.close()
        self.wrapper = None
        self.proxy = None

    def preinit(self):
        """Explicitly called only during acquire if 'initval' is configured"""
        if self.initval is not None:
            self.proxy.set(self.gpio.offset, self.initval)

    @Driver.check_active
    @step(args=['status'])
    def set(self, status):
        self.proxy.set(self.gpio.offset, status)

    @Driver.check_active
    @step(result=True)
    def get(self):
        return self.proxy.get(self.gpio.offset)
