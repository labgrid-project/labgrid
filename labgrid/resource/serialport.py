import attr
from .resource import InfoResource


@attr.s
class SerialPort(InfoResource):
    target = attr.ib()
    port = attr.ib(validator=attr.validators.instance_of(str))
    speed = attr.ib(default=115200, validator=attr.validators.instance_of(int))

    def __attrs_post_init__(self):
        self.target.resources.append(self) #pylint: disable=no-member
