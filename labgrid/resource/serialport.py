import attr

from ..factory import target_factory
from .common import Resource, NetworkResource
from .base import SerialPort


@target_factory.reg_resource
@attr.s(eq=False)
class RawSerialPort(SerialPort, Resource):
    """RawSerialPort describes a serialport which is available on the local computer."""
    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.port is None:
            raise ValueError("RawSerialPort must be configured with a port")

# This does not derive from SerialPort because it is not directly accessible
@target_factory.reg_resource
@attr.s(eq=False)
class NetworkSerialPort(NetworkResource):
    """A NetworkSerialPort is a remotely accessible serialport, usually
    accessed via rfc2217 or tcp raw.

    Args:
        port (str): socket port to connect to
        speed (int): speed of the port e.g. 9800
        protocol (str): connection protocol: "raw" or "rfc2217"
    """
    port = attr.ib(validator=attr.validators.optional(attr.validators.instance_of(int)))
    speed = attr.ib(default=115200, validator=attr.validators.instance_of(int))
    protocol = attr.ib(default="rfc2217", validator=attr.validators.instance_of(str))
