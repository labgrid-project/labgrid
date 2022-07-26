import attr

from ..factory import target_factory
from .common import Resource

@target_factory.reg_resource
@attr.s(eq=False)
class AndroidNetFastboot(Resource):
    address = attr.ib(validator=attr.validators.instance_of(str))
    port = attr.ib(default=5554, validator=attr.validators.instance_of(int))
    protocol = attr.ib(default="udp", validator=attr.validators.instance_of(str))
