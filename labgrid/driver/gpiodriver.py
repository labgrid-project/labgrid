"""All GPIO-related drivers"""
from typing import Union

import attr

from ..factory import target_factory
from ..protocol import DigitalOutputProtocol
from ..resource.base import ManagedGPIO, SysfsGPIO
from ..resource.remote import NetworkManagedGPIO, NetworkSysfsGPIO
from ..resource.udev import MatchedManagedGPIO, MatchedSysfsGPIO
from ..step import step
from .common import Driver
from ..util.agentwrapper import AgentWrapper


@target_factory.reg_driver
@attr.s(eq=False)
class GpioDigitalOutputDriver(Driver, DigitalOutputProtocol):
    gpio: Union[ManagedGPIO, MatchedManagedGPIO, NetworkManagedGPIO, SysfsGPIO, MatchedSysfsGPIO, NetworkSysfsGPIO]

    bindings = {
        "gpio": {
            "ManagedGPIO",
            "MatchedManagedGPIO",
            "NetworkManagedGPIO",
            "SysfsGPIO",
            "MatchedSysfsGPIO",
            "NetworkSysfsGPIO",
        },
    }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.wrapper = None

    def on_activate(self):
        host = self.gpio.host if isinstance(self.gpio, (NetworkSysfsGPIO, NetworkManagedGPIO)) else None

        self.wrapper = AgentWrapper(host)

        self.is_sysfs = isinstance(self.gpio, (SysfsGPIO, MatchedSysfsGPIO, NetworkSysfsGPIO))

        if self.is_sysfs:
            self.proxy = self.wrapper.load('sysfsgpio')
        else:
            self.proxy = self.wrapper.load('managed_gpio')

    def on_deactivate(self):
        self.wrapper.close()
        self.wrapper = None
        self.proxy = None

    @Driver.check_active
    @step(args=['status'])
    def set(self, status: bool) -> None:
        if self.is_sysfs:
            self.proxy.set(self.gpio.index, status)
        else:
            self.proxy.set(self.gpio.chip, self.gpio.pin, status)

    @Driver.check_active
    @step(result=True)
    def get(self) -> bool:
        if self.is_sysfs:
            return self.proxy.get(self.gpio.index)

        return self.proxy.get(self.gpio.chip, self.gpio.pin)
