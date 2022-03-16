import attr

from ..factory import target_factory
from .common import Resource
from .base import SerialPort


@target_factory.reg_resource
@attr.s(eq=False)
class ModbusRTU(SerialPort, Resource):
    """This resource describes Modbus RTU instrument.

    Args:
        port (str): tty the instrument is connected to, e.g. '/dev/ttyUSB0'
        speed (int): optional, default is 115200
        address (int): slave address on the modbus, e.g. 16
        timeout (float): optional, timeout in seconds. Default is 0.25 s
    """

    address = attr.ib(default=None, validator=attr.validators.instance_of(int))
    timeout = attr.ib(default=0.25,
                      validator=attr.validators.instance_of(float))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.port is None:
            raise ValueError("ModbusRTU must be configured with a port")
        if self.address is None:
            raise ValueError("ModbusRTU must be configured with an slave address")
