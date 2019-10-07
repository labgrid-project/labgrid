import attr

from ..factory import target_factory
from .common import Resource


@target_factory.reg_resource
@attr.s(eq=False)
class YKUSHPowerPort(Resource):
    """This resource describes a YEPKIT YKUSH switchable USB hub.

    Args:
        serial (str): serial of the YKUSH device
        index (int): port index"""
    serial = attr.ib(validator=attr.validators.instance_of(str))
    index = attr.ib(validator=attr.validators.instance_of(int),
                    converter=int)
