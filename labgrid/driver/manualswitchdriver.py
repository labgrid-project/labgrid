import attr

from ..factory import target_factory
from ..protocol import DigitalOutputProtocol
from ..step import step
from .common import Driver


@target_factory.reg_driver
@attr.s(eq=False)
class ManualSwitchDriver(Driver, DigitalOutputProtocol):
    description = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str)),
    )

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.status = False

    @Driver.check_active
    @step(args=["status"])
    def set(self, status):
        if self.description is not None:
            description = self.description
        else:
            description = self.name

        self.target.interact(
            "Set {description} for target {name} to {status} and press enter".format(
                description=description,
                name=self.target.name,
                status="ON" if status else "OFF",
            )
        )
        self.status = status

    @Driver.check_active
    @step(result=True)
    def get(self):
        return self.status
