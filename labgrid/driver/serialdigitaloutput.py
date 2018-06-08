import attr

from ..factory import target_factory
from ..protocol import DigitalOutputProtocol
from ..step import step
from .common import Driver
from . import SerialDriver

@target_factory.reg_driver
@attr.s(cmp=False)
class SerialPortDigitalOutputDriver(Driver, DigitalOutputProtocol):
    """
    Controls the state of a GPIO using the control lines of a serial port.

    This driver uses the flow-control pins of a serial port (for example
    an USB-UART-dongle) to control some external power switch. You may connect
    some kind of relay board to the flow control pins.

    The serial port should NOT be used for serial communication at the same
    time. This will probably reset the flow-control signals.

    Usable signals are DTR and RTS.
    """

    bindings = {'serial': SerialDriver}
    signal = attr.ib(validator=attr.validators.instance_of(str))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

        # basic input format checking
        self.signal = self.signal.lower()
        if self.signal not in  ["dtr", "rts"]:
            raise Exception("Unknown index for serial-power-driver")

        self._p = self.serial.serial

    @Driver.check_active
    @step()
    def get(self):
        if self.signal == "dtr":
            return self._p.dtr
        elif self.signal == "rts":
            return self._p.rts

        raise ValueError("Expected signal to be dtr or rts")

    @Driver.check_active
    @step()
    def set(self, value):
        if self.signal == "dtr":
            self._p.dtr = value
        elif self.signal == "rts":
            self._p.rts = value
