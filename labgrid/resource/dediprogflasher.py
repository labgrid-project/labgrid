import attr

from ..factory import target_factory
from .common import NetworkResource, Resource


@target_factory.reg_resource
@attr.s(eq=False)
class DediprogFlasher(Resource):
    vcc = attr.ib(validator=attr.validators.in_(('3.5V', '2.5V', '1.8V')))

@target_factory.reg_resource
@attr.s(eq=False)
class NetworkDediprogFlasher(NetworkResource):
    vcc = attr.ib(validator=attr.validators.in_(('3.5V', '2.5V', '1.8V')))
