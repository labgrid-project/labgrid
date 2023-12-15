import attr

from ..factory import target_factory
from .common import Resource
from .remote import RemoteUSBResource

def validate_protocol(instance, attribute, value):
    if not value.lower() in ("udp", "tcp"):
        raise ValueError("Invalid protocol value - allowed values are 'udp/tcp'")

@target_factory.reg_resource
@attr.s(eq=False)
class NetworkLauterbachDebugger(Resource):
    """The NetworkLauterbachDebug describes a Lauterbach PowerDebug with Ethernet

    Args:
        node (str): Lauterbach NODENAME e.g. IP/NODENAME (factory default: serial number)
        protocol (str): Protocol to use, choice of 'udp/tcp' (default: udp)
    """
    node = attr.ib(validator=attr.validators.instance_of(str))
    protocol = attr.ib(default="udp", validator=attr.validators.in_(("udp", "UDP", "tcp", "TCP")))

    def __attrs_post_init__(self):
        self.host = self.node
        super().__attrs_post_init__()


@target_factory.reg_resource
@attr.s(eq=False)
class RemoteUSBLauterbachDebugger(RemoteUSBResource):
    """The RemoteUSBLauterbachDebugger describes a remotely accessible Lauterbach Debugger connected via USB
    
    Args:
        none
    """
    def __attrs_post_init__(self):
        self.timeout = 10.0
        super().__attrs_post_init__()
