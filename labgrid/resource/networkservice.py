import attr
from ..factory import target_factory
from .resource import InfoResource


@target_factory.reg_resource
@attr.s
class NetworkService(InfoResource):
    address = attr.ib(validator=attr.validators.instance_of(str))
