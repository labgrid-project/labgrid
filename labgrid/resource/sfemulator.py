import attr

from ..factory import target_factory
from .common import NetworkResource, Resource

@target_factory.reg_resource
@attr.s(eq=False)
class SFEmulator(Resource):
    """"This resource describes a Dediprog em100 SPI-Flash Emulator

    This provides serial consoles along with reset control

    Args:
        serial (str): serial number of the em100 device, e.g. DP025143
        chip (str): SPI-flash chip to emulate, e.g. W25Q64CV
    """
    serial = attr.ib(validator=attr.validators.instance_of(str))
    chip = attr.ib(validator=attr.validators.instance_of(str))

@target_factory.reg_resource
@attr.s(eq=False)
class NetworkSFEmulator(NetworkResource):
    """"This resource describes a remote Dediprog em100 SPI-Flash Emulator

    This provides serial consoles along with reset control

    Args:
        serial (str): serial number of the em100 device, e.g. DP025143
        chip (str): SPI-flash chip to emulate, e.g. W25Q64CV
    """
    serial = attr.ib(validator=attr.validators.instance_of(str))
    chip = attr.ib(validator=attr.validators.instance_of(str))
