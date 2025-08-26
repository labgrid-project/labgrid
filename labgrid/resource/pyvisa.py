import attr

from ..factory import target_factory
from .common import Resource, NetworkResource


@target_factory.reg_resource
@attr.s(eq=False)
class PyVISADevice(Resource):
    """The PyVISADevice describes a test stimuli device controlled  with PyVISA

    Args:
        type (str): device resource type following the pyVISA resource syntax, e.g. ASRL, TCPIP...
        url (str, default=''): optional device identifier on selected resource, e.g. <ip> for TCPIP resource
        backend (str, default=''): Visa library backend, e.g. '@sim' for pyvisa-sim backend
    """

    type = attr.ib(validator=attr.validators.instance_of(str))
    url = attr.ib(default="", validator=attr.validators.instance_of(str))
    backend = attr.ib(default="", validator=attr.validators.instance_of(str))

@target_factory.reg_resource
@attr.s(eq=False)
class NetworkPyVISADevice(NetworkResource):
    """The NetworkPyVISADevice describes a remote test stimuli device controlled  with PyVISA

    Args:
        type (str): device resource type following the pyVISA resource syntax, e.g. ASRL, TCPIP...
        url (str, default=''): optional device identifier on selected resource, e.g. <ip> for TCPIP resource
        backend (str, default=''): Visa library backend, e.g. '@sim' for pyvisa-sim backend
    """
    type = attr.ib(validator=attr.validators.instance_of(str))
    url = attr.ib(default="", validator=attr.validators.instance_of(str))
    backend = attr.ib(default="", validator=attr.validators.instance_of(str))
