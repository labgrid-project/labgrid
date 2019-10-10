import enum

import attr

from labgrid.driver import QuartusHPSDriver, SerialDriver
from labgrid.factory import target_factory
from labgrid.protocol import PowerProtocol
from labgrid.step import step
from labgrid.strategy.common import Strategy


@attr.s(eq=False)
class StrategyError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))


class Status(enum.Enum):
    unknown = 0
    flashed_xload = 1
    flashed = 2


@target_factory.reg_driver
@attr.s(eq=False)
class QuartusHPSStrategy(Strategy):
    """QuartusHPSStrategy - Strategy to flash QSPI via 'Quartus Prime Programmer and Tools'"""
    bindings = {
        "power": PowerProtocol,
        "quartushps": QuartusHPSDriver,
        "serial": SerialDriver,
    }

    image = attr.ib(validator=attr.validators.instance_of(str))
    image_xload = attr.ib(validator=attr.validators.instance_of(str))
    status = attr.ib(default=Status.unknown)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    @step(args=['status'])
    def transition(self, status, *, step):
        if not isinstance(status, Status):
            status = Status[status]
        if status == Status.unknown:
            raise StrategyError("can not transition to {}".format(status))
        elif status == self.status:
            step.skip("nothing to do")
            return  # nothing to do
        elif status == Status.flashed_xload:
            self.target.activate(self.power)
            self.power.cycle()
            self.target.activate(self.quartushps)
            # flash bootloader xload image to 0x0
            self.quartushps.flash(self.image_xload, 0x0)
        elif status == Status.flashed:
            self.transition(Status.flashed_xload)
            # flash bootloader image to 0x40000
            self.quartushps.flash(self.image, 0x40000)
            self.power.cycle()
            # activate serial in order to make 'labgrid-client -s $STATE con' work
            self.target.activate(self.serial)
        else:
            raise StrategyError(
                "no transition found from {} to {}".
                format(self.status, status)
            )
        self.status = status
