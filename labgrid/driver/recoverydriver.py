import time

import attr

from ..factory import target_factory
from ..protocol import DigitalOutputProtocol, RecoveryProtocol
from ..step import step
from .common import Driver

@target_factory.reg_driver
@attr.s(eq=False)
class DigitalOutputRecoveryDriver(Driver, RecoveryProtocol):
    """Use a DigitalOutput to assert a recovery signal on the target"""
    bindings = {'output': DigitalOutputProtocol, }
    delay = attr.ib(default=1.0, validator=attr.validators.instance_of(float))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    @Driver.check_active
    @step()
    def set_enable(self, enable):
        if not enable:
            time.sleep(self.delay)
        self.output.set(enable)
