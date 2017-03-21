import enum

import attr

from ..driver import UBootDriver, ShellDriver
from ..protocol import PowerProtocol
from ..factory import target_factory
from .common import Strategy


@attr.s
class StrategyError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))


class Status(enum.Enum):
    unknown = 0
    uboot = 1
    shell = 2


@target_factory.reg_driver
@attr.s
class UBootStrategy(Strategy):
    """UbootStrategy - Strategy to switch to uboot or shell"""
    bindings = {
        "power": PowerProtocol,
        "uboot": UBootDriver,
        "shell": ShellDriver,
    }

    status = attr.ib(default=Status.unknown)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    def transition(self, status):
        if not isinstance(status, Status):
            status = Status[status]
        if status == Status.unknown:
            raise StrategyError("can not transition to {}".format(status))
        elif status == self.status:
            return # nothing to do
        elif status == Status.uboot:
            # cycle power
            self.target.activate(self.power)
            self.power.cycle()
            # interrupt uboot
            self.target.activate(self.uboot)
        elif status == Status.shell:
            # tansition to uboot
            self.transition(Status.uboot)
            self.uboot.boot("")
            self.uboot.await_boot()
            self.target.activate(self.shell)
        else:
            raise StrategyError("no transition found from {} to {}".format(self.status, status))
        self.status = status
