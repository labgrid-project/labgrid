import shlex
import time

import attr

from ..factory import target_factory
from ..protocol import ButtonProtocol, DigitalOutputProtocol
from ..step import step
from ..util.helper import processwrapper
from .common import Driver


@target_factory.reg_driver
@attr.s(eq=False)
class ManualButtonDriver(Driver, ButtonProtocol):
    """ManualButtonDriver - Driver to tell the user to control a target's button"""

    @Driver.check_active
    @step()
    def press(self):
        self.target.interact(
            f"Press and hold the button on target {self.target.name} and press enter"
        )

    @Driver.check_active
    @step()
    def release(self):
        self.target.interact(
            f"Release the button on the target {self.target.name} press enter"
        )

    @Driver.check_active
    @step()
    def press_for(self):
        self.target.interact(
            f"Press and then Release the button on target {self.target.name} for {self.delay} seconds and press enter"
        )

@target_factory.reg_driver
@attr.s(eq=False)
class ExternalButtonDriver(Driver, ButtonProtocol):
    """ExternalButtonDriver - Driver using an external command to control a target's button"""
    cmd_press = attr.ib(validator=attr.validators.instance_of(str))
    cmd_release = attr.ib(validator=attr.validators.instance_of(str))
    cmd_press_for = attr.ib(validator=attr.validators.instance_of(str))
    delay = attr.ib(default=1.0, validator=attr.validators.instance_of(float))

    @Driver.check_active
    @step()
    def press(self):
        cmd = shlex.split(self.cmd_press)
        processwrapper.check_output(cmd)

    @Driver.check_active
    @step()
    def release(self):
        cmd = shlex.split(self.cmd_release)
        processwrapper.check_output(cmd)

    @Driver.check_active
    @step()
    def press_for(self):
        if self.cmd_press_for is not None:
            cmd = shlex.split(self.cmd_press_for)
            processwrapper.check_output(cmd)
        else:
            self.press()
            time.sleep(self.delay)
            self.release()

@target_factory.reg_driver
@attr.s(eq=False)
class DigitalOutputButtonDriver(Driver, ButtonProtocol):
    """
    DigitalOutputButtonDriver uses a DigitalOutput to control a button
    """
    bindings = {"output": DigitalOutputProtocol, }
    delay = attr.ib(default=1.0, validator=attr.validators.instance_of(float))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    @Driver.check_active
    @step()
    def press(self):
        self.output.set(True)

    @Driver.check_active
    @step()
    def release(self):
        self.output.set(False)

    @Driver.check_active
    @step()
    def press_for(self):
        self.press()
        time.sleep(self.delay)
        self.release()

    @Driver.check_active
    @step()
    def get(self):
        return self.output.get()
