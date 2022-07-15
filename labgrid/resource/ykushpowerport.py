import attr

from ..factory import target_factory
from .common import NetworkResource


@target_factory.reg_resource
@attr.s(eq=False)
class YKUSHPowerPort(NetworkResource):
    """This resource describes a YEPKIT YKUSH switchable USB hub.

    Args:
        serial (str): serial of the YKUSH device
        index (int): port index"""
    serial = attr.ib(validator=attr.validators.instance_of(str))
    index = attr.ib(validator=attr.validators.instance_of(int),
                    converter=int)
