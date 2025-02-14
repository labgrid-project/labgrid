import attr

from ..factory import target_factory
from .common import NetworkResource


@target_factory.reg_resource
@attr.s(eq=False)
class IPMIInterface(NetworkResource):
    """This resource describes a IPMI interface.

    Args:
        host (str): address for IPMI interface
        username (str): IPMI session username
        password (str): IPMI session password
        port (int): network port for IPMI (Default=623)
        interface (str): The IPMI interface type to use (Default=lanplus)"""

    username = attr.ib(validator=attr.validators.instance_of(str))
    password = attr.ib(validator=attr.validators.instance_of(str))
    port = attr.ib(default=623, validator=attr.validators.instance_of(int))
    interface = attr.ib(default="lanplus", validator=attr.validators.instance_of(str))
