import attr

from ..factory import target_factory
from .common import Resource


@target_factory.reg_resource
@attr.s(eq=False)
class LAASerialPort(Resource):
    """This resource describes a serial port on a DUT connected via LAA.

    Args:
        laa_identity (str): LAA identity for connection
        serial_name (str): name of the serial port on the LAA"""
    laa_identity = attr.ib(validator=attr.validators.instance_of(str))
    serial_name = attr.ib(validator=attr.validators.instance_of(str))


@target_factory.reg_resource
@attr.s(eq=False)
class LAAPowerPort(Resource):
    """This resource describes a power port on a DUT connected via LAA.

    Args:
        laa_identity (str): LAA identity for connection
        power_on (list): sequence of (vbus, state) tuples for power on
        power_off (list): sequence of (vbus, state) tuples for power off
        power_cycle (list): optional sequence for power cycle"""
    laa_identity = attr.ib(validator=attr.validators.instance_of(str))
    power_on = attr.ib(validator=attr.validators.instance_of(list))
    power_off = attr.ib(validator=attr.validators.instance_of(list))
    power_cycle = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(list)),
    )
    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        for name in ("power_on", "power_off"):
            self._check_power_sequence(name, getattr(self, name))
        if self.power_cycle is not None:
            self._check_power_sequence("power_cycle", self.power_cycle)

    @staticmethod
    def _check_power_sequence(name, seq):
        for i, entry in enumerate(seq):
            if not isinstance(entry, (list, tuple)) or len(entry) != 2:
                raise ValueError(
                    f"{name}[{i}] must be [vbus, state], got {entry!r}"
                )
            if not isinstance(entry[0], str) or not isinstance(entry[1], str):
                raise ValueError(
                    f"{name}[{i}] must be [str, str], got {entry!r}"
                )


@target_factory.reg_resource
@attr.s(eq=False)
class LAAUSBGadgetMassStorage(Resource):
    """This resource describes a USB gadget mass storage device on a LAA.

    Args:
        laa_identity (str): LAA identity for connection
        image (str): mass storage image filename"""
    laa_identity = attr.ib(validator=attr.validators.instance_of(str))
    image = attr.ib(validator=attr.validators.instance_of(str))


@target_factory.reg_resource
@attr.s(eq=False)
class LAAUSBPort(Resource):
    """This resource describes USB ports on a DUT connected via LAA.

    Args:
        laa_identity (str): LAA identity for connection
        usb_ports (list): list of USB port numbers to control"""
    laa_identity = attr.ib(validator=attr.validators.instance_of(str))
    usb_ports = attr.ib(validator=attr.validators.instance_of(list))


@target_factory.reg_resource
@attr.s(eq=False)
class LAAButtonPort(Resource):
    """This resource describes virtual buttons on a DUT connected via LAA.

    Args:
        laa_identity (str): LAA identity for connection
        buttons (list): list of button names available"""
    laa_identity = attr.ib(validator=attr.validators.instance_of(str))
    buttons = attr.ib(validator=attr.validators.instance_of(list))


@target_factory.reg_resource
@attr.s(eq=False)
class LAALed(Resource):
    """This resource describes a LED on a DUT connected via LAA.

    Args:
        laa_identity (str): LAA identity for connection"""
    laa_identity = attr.ib(validator=attr.validators.instance_of(str))


@target_factory.reg_resource
@attr.s(eq=False)
class LAATempSensor(Resource):
    """This resource describes a temperature sensor on a DUT connected via LAA.

    Args:
        laa_identity (str): LAA identity for connection"""
    laa_identity = attr.ib(validator=attr.validators.instance_of(str))


@target_factory.reg_resource
@attr.s(eq=False)
class LAAWattMeter(Resource):
    """This resource describes a power meter on a DUT connected via LAA.

    Args:
        laa_identity (str): LAA identity for connection"""
    laa_identity = attr.ib(validator=attr.validators.instance_of(str))


@target_factory.reg_resource
@attr.s(eq=False)
class LAAProvider(Resource):
    """This resource describes file storage on an LAA for TFTP provisioning.

    Args:
        laa_identity (str): LAA identity for connection"""
    laa_identity = attr.ib(validator=attr.validators.instance_of(str))


