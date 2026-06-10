import attr

from ..factory import target_factory
from .common import NetworkResource, Resource


@target_factory.reg_resource
@attr.s(eq=False)
class YKUSHPowerPort(Resource):
    """This resource describes a YEPKIT YKUSH switchable USB hub.

    Args:
        serial (str): serial of the YKUSH device
        index (str): port index"""

    serial = attr.ib(validator=attr.validators.instance_of(str))
    index = attr.ib(validator=attr.validators.instance_of(str), converter=str)


@target_factory.reg_resource
@attr.s(eq=False)
class NetworkYKUSHPowerPort(NetworkResource):
    """ "This resource describes a remote YEPKIT YKUSH switchable USB hub.

    Args:
        serial (str): serial of the YKUSH device
        index (str): port index"""

    serial = attr.ib(validator=attr.validators.instance_of(str))
    index = attr.ib(validator=attr.validators.instance_of(str), converter=str)
