import attr

from ..factory import target_factory
from .common import Resource


@target_factory.reg_resource
@attr.s
class NetworkPowerPort(Resource):
    model = attr.ib(validator=attr.validators.instance_of(str))
    host = attr.ib(validator=attr.validators.instance_of(str))
    index = attr.ib(validator=attr.validators.instance_of(str),
                    convert=lambda x: str(int(x)))
