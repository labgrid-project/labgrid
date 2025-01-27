"""All GPIO-related drivers"""
import attr
import time

from ..factory import target_factory
from ..protocol import DigitalOutputProtocol, ResetProtocol, PowerProtocol, ButtonProtocol
from ..resource.remote import NetworkSysfsGPIO
from ..step import step
from .common import Driver
from ..util.agentwrapper import AgentWrapper


@target_factory.reg_driver
@attr.s(eq=False)
class GpioDigitalOutputDriver(Driver, DigitalOutputProtocol, ResetProtocol, PowerProtocol, ButtonProtocol):

    bindings = {
        "gpio": {"SysfsGPIO", "NetworkSysfsGPIO"},
    }
    delay = attr.ib(default=1.0, validator=attr.validators.instance_of(float))

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
        self.proxy.set(self.gpio.index, self.gpio.invert, status)

    @Driver.check_active
    @step(result=True)
    def get(self):
        return self.proxy.get(self.gpio.index, self.gpio.invert)

    @Driver.check_active
    @step(result=True)
    def invert(self):
        self.set(not self.get())

    @Driver.check_active
    @step(result=True)
    def reset(self):
        self.cycle()

    @Driver.check_active
    @step(result=True)
    def on(self):
        self.set(True)

    @Driver.check_active
    @step(result=True)
    def off(self):
        self.set(False)

    @Driver.check_active
    @step(result=True)
    def cycle(self):
        self.off()
        time.sleep(self.delay)
        self.on()

    @Driver.check_active
    @step(result=True)
    def press(self):
        self.set(True)

    @Driver.check_active
    @step(result=True)
    def release(self):
        self.set(False)

    @Driver.check_active
    @step(result=True)
    def press_for(self):
        self.press()
        time.sleep(self.delay)
        self.release()
