import attr
import subprocess
import time
from ..protocol import PowerProtocol
from .exception import NoDriveError


@attr.s
class ManualPowerDriver(PowerProtocol):
    """ManualPowerDriver - Driver to tell the user to control a target's power"""
    name = attr.ib(validator=attr.validators.instance_of(str))

    def on(self):
        input("Turn the target {name} ON and press enter".format(name=self.name))

    def off(self):
        input("Turn the target {name} OFF and press enter".format(name=self.name))

    def cycle(self):
        input("CYCLE the target {name} and press enter".format(name=self.name))


def _external_cmd(instance, attribute, value):
    attr.validators.instance_of(str)(instance, attribute, value)
    if not '{name}' in value:
        raise ValueError(
            "'{name}' must contain a {{name}} placeholder which '{value}' doesn't."
            .format(name=attribute.name, value=value),
        )

@attr.s
class ExternalPowerDriver(PowerProtocol):
    """ExternalPowerDriver- Driver using an external command to control a target's power"""
    name = attr.ib(validator=attr.validators.instance_of(str))
    cmd_on = attr.ib(validator=_external_cmd)
    cmd_off = attr.ib(validator=_external_cmd)
    cmd_cycle = attr.ib(default=None, validator=attr.validators.optional(_external_cmd))
    delay = attr.ib(default=1.0, validator=attr.validators.instance_of(float))

    def on(self):
        subprocess.check_call(self.cmd_on.format(name=self.name))

    def off(self):
        subprocess.check_call(self.cmd_off.format(name=self.name))

    def cycle(self):
        if self.cmd_cycle is not None:
            subprocess.check_call(self.cmd_cycle.format(name=self.name))
        else:
            self.off()
            time.sleep(self.delay)
            self.on()
