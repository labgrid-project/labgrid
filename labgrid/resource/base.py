import attr

from .common import Resource


@attr.s
class SerialPort(Resource):
    """The basic SerialPort describes port and speed

    Args:
        port (str): port to connect to
        speed (int): speed of the port, defaults to 115200"""
    port = attr.ib(default=None)
    speed = attr.ib(default=115200, validator=attr.validators.instance_of(int))


@attr.s
class EthernetInterface(Resource):
    """The basic EthernetInterface contains an interfacename

    Args:
        ifname (str): name of the interface"""
    ifname = attr.ib(default=None)
