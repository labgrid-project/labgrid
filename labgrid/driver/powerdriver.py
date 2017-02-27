import subprocess
import time
from importlib import import_module

import attr

from ..factory import target_factory
from ..protocol import PowerProtocol, DigitalOutputProtocol
from ..resource import NetworkPowerPort
from .common import Driver
from .onewiredriver import OneWirePIODriver


@target_factory.reg_driver
@attr.s
class ManualPowerDriver(Driver, PowerProtocol):
    """ManualPowerDriver - Driver to tell the user to control a target's power"""
    name = attr.ib(validator=attr.validators.instance_of(str))

    def on(self):
        self.target.interact(
            "Turn the target {name} ON and press enter".format(name=self.name)
        )

    def off(self):
        self.target.interact(
            "Turn the target {name} OFF and press enter".
            format(name=self.name)
        )

    def cycle(self):
        self.target.interact(
            "CYCLE the target {name} and press enter".format(name=self.name)
        )


@target_factory.reg_driver
@attr.s
class ExternalPowerDriver(Driver, PowerProtocol):
    """ExternalPowerDriver - Driver using an external command to control a target's power"""
    cmd_on = attr.ib(validator=attr.validators.instance_of(str))
    cmd_off = attr.ib(validator=attr.validators.instance_of(str))
    cmd_cycle = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str))
    )
    delay = attr.ib(default=2.0, validator=attr.validators.instance_of(float))

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

@target_factory.reg_driver
@attr.s
class NetworkPowerDriver(Driver, PowerProtocol):
    """NetworkPowerDriver - Driver using a networked power switch to control a target's power"""
    bindings = {"port": NetworkPowerPort, }
    delay = attr.ib(default=2.0, validator=attr.validators.instance_of(float))


    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        # TODO: allow backends to register models with other names
        self.backend = import_module(
            ".power.{}".format(self.port.model),
            __package__
        )

    def on(self):
        self.backend.set(self.port.host, self.port.index, True)

    def off(self):
        self.backend.set(self.port.host, self.port.index, False)

    def cycle(self):
        def fallback():
            self.off()
            time.sleep(self.delay)
            self.on()

        cycle = getattr(self.backend, 'cycle', fallback)
        cycle()

    def get(self):
        return self.backend.get(self.port.host, self.port.index)

@target_factory.reg_driver
@attr.s
class DigitalOutputPowerDriver(Driver, PowerProtocol):
    """DigitalOutputPowerDriver - Driver using a DigitalOutput to reset the target and
    subprocesses to turn it on and off"""
    bindings = {"output": DigitalOutputProtocol, }
    cmd_on = attr.ib(validator=attr.validators.instance_of(str))
    cmd_off = attr.ib(validator=attr.validators.instance_of(str))
    delay = attr.ib(default=1.0, validator=attr.validators.instance_of(float))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    def on(self):
        subprocess.check_call(self.cmd_on)

    def off(self):
        subprocess.check_call(self.cmd_off)

    def cycle(self):
        self.output.set(True)
        time.sleep(self.delay)
        self.output.set(False)

    def get(self):
        return True
