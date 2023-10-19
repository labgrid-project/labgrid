import attr

from ..factory import target_factory
from .base import CANPort
from .common import Resource


@target_factory.reg_resource
@attr.s(eq=False)
class RawCANPort(CANPort, Resource):
    """RawCANPort describes a CAN port which is available on the local computer."""
    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.ifname is None:
            raise ValueError("RawCANPort must be configured with an interface name")
