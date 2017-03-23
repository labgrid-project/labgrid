import attr

from ..factory import target_factory
from .common import Resource


@target_factory.reg_resource
@attr.s
class NetworkPowerPort(Resource):
    """The NetworkPowerPort describes a remotely switchable PowerPort

    Args:
        model (str): model of the external power switch
        host (str): host to connect to
        index (str): index of the power port on the external switch
    """
    model = attr.ib(validator=attr.validators.instance_of(str))
    host = attr.ib(validator=attr.validators.instance_of(str))
    index = attr.ib(validator=attr.validators.instance_of(str),
                    convert=lambda x: str(int(x)))
