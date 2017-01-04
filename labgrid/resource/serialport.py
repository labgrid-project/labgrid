import attr

from ..factory import target_factory
from .common import Resource


@target_factory.reg_resource
@attr.s
class SerialPort(Resource):
    port = attr.ib(validator=attr.validators.instance_of(str))
    speed = attr.ib(default=115200, validator=attr.validators.instance_of(int))
