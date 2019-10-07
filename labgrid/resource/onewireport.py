import attr

from ..factory import target_factory
from .common import Resource


@target_factory.reg_resource
@attr.s(eq=False)
class OneWirePIO(Resource):
    """This resource describes a Onewire PIO Port.

    Args:
        host (str): hostname of the owserver e.g. localhost:4304
        path (str): path to the port on the owserver e.g. 29.7D6913000000/PIO.0
        invert (bool): optional, whether the logic level is be inverted (active-low)"""
    host = attr.ib(validator=attr.validators.instance_of(str))
    path = attr.ib(validator=attr.validators.instance_of(str))
    invert = attr.ib(default=False, validator=attr.validators.instance_of(bool))
