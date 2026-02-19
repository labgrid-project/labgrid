import attr

from .common import Driver
from .modbusrtudriver import ModbusRTUDriver
from ..factory import target_factory
from ..step import step
from ..protocol import DigitalOutputProtocol


@target_factory.reg_driver
@attr.s(eq=False)
class WaveshareRTURelaisDriver(ModbusRTUDriver, DigitalOutputProtocol):
    bindings = {"resource": {"SerialPort", "NetworkSerialPort"}}

    relais = attr.ib(default=0, validator=attr.validators.instance_of(int))
    no_channel = attr.ib(default=8, validator=attr.validators.instance_of(int))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    def on_activate(self):
        super().on_activate()

    def on_deactivate(self):
        super().on_deactivate()

    @Driver.check_active
    @step(args=["status"])
    def set(self, status):
        _status = 1 if status else 0
        self.write_bit(self.relais, _status)

    @Driver.check_active
    @step(result=True)
    def get(self):
        status = self.read_bits(0x00, number_of_bits=self.no_channel, functioncode=1)
        return status[self.relais]
