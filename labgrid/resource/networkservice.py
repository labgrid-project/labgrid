import attr

from ..factory import target_factory
from .common import Resource


@target_factory.reg_resource
@attr.s(eq=False)
class NetworkService(Resource):
    address = attr.ib(validator=attr.validators.instance_of(str))
    username = attr.ib(validator=attr.validators.instance_of((str,list)))
    password = attr.ib(default='', validator=attr.validators.instance_of((str,list)))
    port = attr.ib(default=22, validator=attr.validators.instance_of(int))
