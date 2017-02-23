import attr

from ..factory import target_factory
from .common import Resource


@target_factory.reg_resource
@attr.s
class OneWirePIO(Resource):
    """This resource describes a Onewire PIO Port.

    Arguments:
    host - The hostname of the owserver e.g. localhost:4304
    path - Path to the port on the owserver e.g. 29.7D6913000000/PIO.0"""
    host = attr.ib(validator=attr.validators.instance_of(str))
    path = attr.ib(validator=attr.validators.instance_of(str))
