import time

import attr

from ..factory import target_factory
from ..protocol import DigitalOutputProtocol, ResetProtocol
from ..step import step
from .common import Driver

@target_factory.reg_driver
@attr.s(eq=False)
class DigitalOutputResetDriver(Driver, ResetProtocol):
    """DigitalOutputResetDriver - Driver using a DigitalOutput to reset the
    target"""
    bindings = {"output": DigitalOutputProtocol, }
    delay = attr.ib(default=1.0, validator=attr.validators.instance_of(float))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    @Driver.check_active
    @step()
    def reset(self):
        self.output.set(True)
        time.sleep(self.delay)
        self.output.set(False)
