"""All GPIO-related drivers"""
import attr

from ..factory import target_factory
from ..protocol import DigitalOutputProtocol
from ..step import step
from .common import Driver


@target_factory.reg_driver
@attr.s(cmp=False)
class GpioDigitalOutputDriver(Driver, DigitalOutputProtocol):
    """
    Controls the state of a GPIO using libgpiod.

    Takes a string property 'chip' which refers to the GPIO device.
    You can use its path, name, label or number (default: 0).
    The offset to the GPIO line is set by the integer property 'offset'.
    """

    bindings = {}
    offset = attr.ib(validator=attr.validators.instance_of(int))
    chip = attr.ib(default="0", validator=attr.validators.instance_of(str))
    gpio_chip = None
    gpio_state = True

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    def on_activate(self):
        import gpiod
        self.gpio_chip = gpiod.Chip(self.chip)
        gpio_line = self.gpio_chip.get_line(self.offset)
        gpio_line.request("labgrid", gpiod.LINE_REQ_DIR_OUT)

    def on_deactivate(self):
        gpio_line = self.gpio_chip.get_line(self.offset)
        gpio_line.release()
        self.gpio_chip.close()

    @Driver.check_active
    @step()
    def get(self):
        return self.gpio_state

    @Driver.check_active
    @step()
    def set(self, status):
        gpio_line = self.gpio_chip.get_line(self.offset)
        gpio_line.set_value(int(status))
        self.gpio_state = status
