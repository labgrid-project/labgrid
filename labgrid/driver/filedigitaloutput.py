import os

import attr

from ..factory import target_factory
from ..protocol import DigitalOutputProtocol
from ..step import step
from .common import Driver


@target_factory.reg_driver
@attr.s(eq=False)
class FileDigitalOutputDriver(Driver, DigitalOutputProtocol):
    """
    Two arbitrary string values false_repr and true_repr
    are defined as representations for False and True.
    These values are written to a file and read from it.
    If the file's content does not match any of the
    representations it defaults to False.
    A prime example for using this driver is Linux's sysfs.
    """

    filepath = attr.ib(validator=attr.validators.instance_of(str))
    false_repr = attr.ib(default='0\n', validator=attr.validators.instance_of(str))
    true_repr = attr.ib(default='1\n', validator=attr.validators.instance_of(str))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

        if not os.path.isfile(self.filepath):
            raise Exception(f"{self.filepath} is not a file.")

    @Driver.check_active
    @step()
    def get(self):
        with open(self.filepath) as fdes:
            from_file = fdes.read()
        return from_file == self.true_repr

    @Driver.check_active
    @step()
    def set(self, status):
        out = self.true_repr if status else self.false_repr
        with open(self.filepath, "w") as fdes:
            fdes.write(out)
