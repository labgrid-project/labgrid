import attr

from ..factory import target_factory
from .common import Resource


@target_factory.reg_resource
@attr.s
class NetworkService(Resource):
    address = attr.ib(validator=attr.validators.instance_of(str))
    username = attr.ib(validator=attr.validators.instance_of(str))
