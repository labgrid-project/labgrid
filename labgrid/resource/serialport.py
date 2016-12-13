import attr
from .resource import InfoResource


@attr.s
class SerialPort(InfoResource):
    port = attr.ib(validator=attr.validators.instance_of(str))
    speed = attr.ib(default=115200, validator=attr.validators.instance_of(int))
