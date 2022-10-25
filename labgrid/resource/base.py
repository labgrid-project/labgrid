import attr

from ..factory import target_factory
from .common import Resource


@attr.s(eq=False)
class SerialPort(Resource):
    """The basic SerialPort describes port and speed

    Args:
        port (str): port to connect to
        speed (int): speed of the port, defaults to 115200"""
    port = attr.ib(default=None)
    speed = attr.ib(default=115200, validator=attr.validators.instance_of(int))


@target_factory.reg_resource
@attr.s(eq=False)
class NetworkInterface(Resource):
    """The basic NetworkInterface contains an interface name

    Args:
        ifname (str): name of the interface"""
    ifname = attr.ib(default=None)

@target_factory.reg_resource
@attr.s
class EthernetPort(Resource):
    """The basic EthernetPort describes a switch and interface

    Args:
        switch (str): name of the switch
        interface (str): name of the interface"""
    switch = attr.ib(default=None)
    interface = attr.ib(default=None)


@target_factory.reg_resource
@attr.s(eq=False)
class SysfsGPIO(Resource):
    """The basic SysfsGPIO contains an index

    Args:
        index (int): index of target gpio line."""
    index = attr.ib(default=None, validator=attr.validators.instance_of(int))
