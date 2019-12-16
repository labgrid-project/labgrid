import attr

from ..factory import target_factory
from .common import Resource


@target_factory.reg_resource
@attr.s(eq=False)
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
                    converter=lambda x: str(int(x)))


@target_factory.reg_resource
@attr.s(eq=False)
class PDUDaemonPort(Resource):
    """The PDUDaemonPort describes a port on a PDU accessible via PDUDaemon

    Args:
        host (str): name of the host running the PDUDaemon
        pdu (str): name of the PDU in the configuration file
        index (int): index of the power port on the PDU
    """
    host = attr.ib(validator=attr.validators.instance_of(str))
    pdu = attr.ib(validator=attr.validators.instance_of(str))
    index = attr.ib(validator=attr.validators.instance_of(int), converter=int)
