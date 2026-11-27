import attr

from ..factory import target_factory
from .common import Resource
from .remote import RemoteUSBResource


def validate_protocol(instance, attribute, value):
    if not value.lower() in ("udp", "tcp"):
        raise ValueError("Invalid protocol value - allowed values are `UDP`/`TCP`")


@target_factory.reg_resource
@attr.s(eq=False)
class NetworkLauterbachDebugger(Resource):
    """The NetworkLauterbachDebug describes a Lauterbach PowerDebug with Ethernet

    Args:
        node (str): Lauterbach NODENAME e.g. IP/NODENAME (factory default: serial number)
        protocol (str, default="UDP"): Protocol to use, must be one of:
           TCP: select TCP-based protocol - enables LG_PROXY support, requires recent device
           UDP: select UDP-based protocol - works with legacy devices
    """
    node = attr.ib(validator=attr.validators.instance_of(str))
    protocol = attr.ib(default="UDP", validator=attr.validators.in_(("udp", "UDP", "tcp", "TCP")))

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
