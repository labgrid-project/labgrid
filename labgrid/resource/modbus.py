import attr

from ..factory import target_factory
from .common import Resource


@target_factory.reg_resource
@attr.s(cmp=False)
class ModbusTCPCoil(Resource):
    """This resource describes Modbus TCP coil.

    Args:
        host (str): hostname of the Modbus TCP server e.g. "192.168.23.42:502"
        coil (int): index of the coil e.g. 3"""
    host = attr.ib(validator=attr.validators.instance_of(str))
    coil = attr.ib(validator=attr.validators.instance_of(int))
