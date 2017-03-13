import attr

from .common import Resource


@attr.s
class SerialPort(Resource):
    port = attr.ib(default=None)
    speed = attr.ib(default=115200, validator=attr.validators.instance_of(int))


@attr.s
class EthernetInterface(Resource):
    ifname = attr.ib(default=None)
