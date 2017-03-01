import attr

from ..factory import target_factory
from .common import Resource
from .base import SerialPort


@target_factory.reg_resource
@attr.s
class RawSerialPort(SerialPort, Resource):
    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.port is None:
            ValueError("RawSerialPort must be configured with a port")

# This does not derive from SerialPort because it is not directly accessible
@target_factory.reg_resource
@attr.s
class NetworkSerialPort(Resource):
    host = attr.ib(validator=attr.validators.instance_of(str))
    port = attr.ib(validator=attr.validators.instance_of(int))
    speed = attr.ib(default=115200, validator=attr.validators.instance_of(int))
