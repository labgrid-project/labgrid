import attr

from ..factory import target_factory
from .common import Resource, NetworkResource
from .base import SerialPort


@target_factory.reg_resource
@attr.s
class RawSerialPort(SerialPort, Resource):
    """RawSerialPort describes a serialport which is vailable on the local computer."""
    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.port is None:
            ValueError("RawSerialPort must be configured with a port")

# This does not derive from SerialPort because it is not directly accessible
@target_factory.reg_resource
@attr.s
class NetworkSerialPort(NetworkResource):
    """A NetworkSerialPort is a remotely accessable serialport, usually
    accessed via rfc2217.

    Args:
        port (str): connection string to the port e.g. 'rfc2217://<host>:<port>'
        speed (int): speed of the port e.g. 9800"""
    port = attr.ib(validator=attr.validators.optional(attr.validators.instance_of(int)))
    speed = attr.ib(default=115200, validator=attr.validators.instance_of(int))
