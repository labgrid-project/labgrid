import attr

from ..factory import target_factory
from .common import NetworkResource, Resource


@target_factory.reg_resource
@attr.s(eq=False)
class Flashrom(Resource):
    """Programmer is the programmer parameter described in man(8) of flashrom"""
    programmer = attr.ib(validator=attr.validators.instance_of(str))

@target_factory.reg_resource
@attr.s(eq=False)
class NetworkFlashrom(NetworkResource):
    programmer = attr.ib(validator=attr.validators.instance_of(str))
