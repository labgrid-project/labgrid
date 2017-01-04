import subprocess
import time

import attr

from ..factory import target_factory
from ..protocol import PowerProtocol
from .exception import NoDriverError


@target_factory.reg_driver
@attr.s
class ManualPowerDriver(PowerProtocol):
    """ManualPowerDriver - Driver to tell the user to control a target's power"""
    target = attr.ib()
    name = attr.ib(validator=attr.validators.instance_of(str))

    def on(self):
        input(
            "Turn the target {name} ON and press enter".format(name=self.name)
        )

    def off(self):
        input(
            "Turn the target {name} OFF and press enter".
            format(name=self.name)
        )

    def cycle(self):
        input("CYCLE the target {name} and press enter".format(name=self.name))


@target_factory.reg_driver
@attr.s
class ExternalPowerDriver(PowerProtocol):
    """ExternalPowerDriver- Driver using an external command to control a target's power"""
    target = attr.ib()
    cmd_on = attr.ib(validator=attr.validators.instance_of(str))
    cmd_off = attr.ib(validator=attr.validators.instance_of(str))
    cmd_cycle = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str))
    )
    delay = attr.ib(default=1.0, validator=attr.validators.instance_of(float))

    def on(self):
        subprocess.check_call(self.cmd_on)

    def off(self):
        subprocess.check_call(self.cmd_off)

    def cycle(self):
        if self.cmd_cycle is not None:
            subprocess.check_call(self.cmd_cycle)
        else:
            self.off()
            time.sleep(self.delay)
            self.on()
