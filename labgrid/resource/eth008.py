import attr

from ..factory import target_factory
from .common import Resource


@target_factory.reg_resource
@attr.s(eq=False)
class Eth008DigitalOutput(Resource):
    """This resource describes a digital output on an ETH008 relay board.

    Args:
        host (str): host to connect to
        index (str): index of the relay on the ETH008 board (1-8)
        invert (bool): whether to invert the output (default: False)
    """
    host = attr.ib(validator=attr.validators.instance_of(str))
    index = attr.ib(validator=attr.validators.instance_of(str),
                    converter=lambda x: str(int(x)))
    invert = attr.ib(default=False, validator=attr.validators.instance_of(bool))
