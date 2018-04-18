import attr

from ..factory import target_factory
from ..protocol import DigitalOutputProtocol
from ..step import step
from .common import Driver

@target_factory.reg_driver
@attr.s(cmp=False)
class SysfsDigitalOutputDriver(Driver, DigitalOutputProtocol):
    """
    Controls a GPIO using the Linux /sys/class/gpio - interface.

    Outputs are identified using their ID.

    A given pin will be exported as GPIO and set as output during setup.

    The used part of the sysfs needs to be writeable by the user running labgrid.
    """

    signal = attr.ib(validator=attr.validators.instance_of(str))
    initial_state = attr.ib(default=False, validator=attr.validators.instance_of(bool))
    inverted = attr.ib(default=False, validator=attr.validators.instance_of(bool))

    @staticmethod
    def _sysfs_write(endpoint, value):
        with open("/sys/class/gpio/" + endpoint, "w") as fh:
            fh.write(value)

    @staticmethod
    def _sysfs_read(endpoint):
        with open("/sys/class/gpio/" + endpoint, "r") as fh:
            return fh.read()

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

        # export pin
        try:
            SysfsDigitalOutputDriver._sysfs_write("export", self.signal)
        except OSError as e:
            if e.errno == 16:
                # pin was already exported. We can ignore this.
                pass
            else:
                raise e

        # set to output
        if self.inverted:
            local_initial_state = not self.initial_state
        else:
            local_initial_state = self._initial_state
        local_initial_state = "high" if local_initial_state else "low"
        SysfsDigitalOutputDriver._sysfs_write("gpio{}/direction".format(self.signal), local_initial_state)

    @Driver.check_active
    @step()
    def get(self):
        state = SysfsDigitalOutputDriver._sysfs_read("gpio{}/value".format(self.signal)).strip()
        return True if state == "1" else False

    @Driver.check_active
    @step()
    def set(self, value):
        if self.inverted:
            value = not value
        self._state = value
        out = "1" if value else "0"
        SysfsDigitalOutputDriver._sysfs_write("gpio{}/value".format(self.signal), out)
