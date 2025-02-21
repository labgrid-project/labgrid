import attr

from ..factory import target_factory
from ..protocol import DigitalOutputProtocol
from ..step import step
from .common import Driver

@target_factory.reg_driver
@attr.s(eq=False)
class ButtonDriver(Driver):
    """ButtonDriver - Driver using a DigitalOutput to push a button"""
    bindings = {"output": DigitalOutputProtocol, }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    @Driver.check_active
    @step(args=['status'])
    def set(self, status):
        self.output.set(status)

    @Driver.check_active
    @step(result=True)
    def get(self):
        return self.output.get()
