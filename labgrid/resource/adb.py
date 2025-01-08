import attr

from ..factory import target_factory
from .common import NetworkResource, Resource


@target_factory.reg_resource
@attr.s(eq=False)
class ADBDevice(Resource):
    serialno = attr.ib(validator=attr.validators.instance_of(str))


@target_factory.reg_resource
@attr.s(eq=False)
class NetworkADBDevice(NetworkResource):
    serialno = attr.ib(validator=attr.validators.instance_of(str))
    port = attr.ib(converter=int, validator=attr.validators.instance_of(int))


@target_factory.reg_resource
@attr.s(eq=False)
class RemoteADBDevice(NetworkResource):
    port = attr.ib(converter=int, validator=attr.validators.instance_of(int))
