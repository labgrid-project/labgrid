import enum

import attr

from ..driver import ShellDriver
from ..factory import target_factory
from ..protocol import PowerProtocol
from ..step import step
from .common import Strategy, StrategyError


class Status(enum.Enum):
    unknown = 0
    off = 1
    shell = 2


@target_factory.reg_driver
@attr.s(cmp=False)
class ShellStrategy(Strategy):
    """ShellStrategy - Strategy to switch to shell"""
    bindings = {
        "power": PowerProtocol,
        "shell": ShellDriver,
    }

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
        elif status == Status.off:
            self.target.deactivate(self.shell)
            self.target.activate(self.power)
            self.power.off()
        elif status == Status.shell:
            self.transition(Status.off)  # pylint: disable=missing-kwoa
            self.power.cycle()
            self.target.activate(self.shell)
        else:
            raise StrategyError(
                "no transition found from {} to {}".
                format(self.status, status)
            )
        self.status = status
