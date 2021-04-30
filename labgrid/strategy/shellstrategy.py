import enum

import attr

from ..factory import target_factory
from ..step import step
from .common import Strategy, StrategyError


class Status(enum.Enum):
    unknown = 0
    off = 1
    shell = 2


@target_factory.reg_driver
@attr.s(eq=False)
class ShellStrategy(Strategy):
    """ShellStrategy - Strategy to switch to shell"""
    bindings = {
        "power": "PowerProtocol",
        "console": "ConsoleProtocol",
        "shell": "ShellDriver",
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
            self.target.deactivate(self.console)
            self.target.activate(self.power)
            self.power.off()
        elif status == Status.shell:
            self.transition(Status.off)  # pylint: disable=missing-kwoa
            self.target.activate(self.console)
            self.power.cycle()
            self.target.activate(self.shell)
        else:
            raise StrategyError(
                "no transition found from {} to {}".
                format(self.status, status)
            )
        self.status = status

    @step(args=['status'])
    def force(self, status, *, step):
        if not isinstance(status, Status):
            status = Status[status]
        if status == Status.unknown:
            raise StrategyError("can not force state {}".format(status))
        elif status == Status.off:
            self.target.deactivate(self.shell)
            self.target.activate(self.power)
        elif status == Status.shell:
            self.target.activate(self.power)
            self.target.activate(self.shell)
        else:
            raise StrategyError("not setup found for {}".format(status))
        self.status = status
