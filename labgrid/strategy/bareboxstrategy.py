import enum

import attr

from ..factory import target_factory
from ..step import step
from .common import Strategy, StrategyError


class Status(enum.Enum):
    unknown = 0
    off = 1
    barebox = 2
    shell = 3


@target_factory.reg_driver
@attr.s(eq=False)
class BareboxStrategy(Strategy):
    """BareboxStrategy - Strategy to switch to barebox or shell"""
    bindings = {
        "power": "PowerProtocol",
        "console": "ConsoleProtocol",
        "barebox": "BareboxDriver",
        "shell": "ShellDriver",
    }

    status = attr.ib(default=Status.unknown)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    @step(args=['status'])
    def transition(self, status, *, step):  # pylint: disable=redefined-outer-name
        if not isinstance(status, Status):
            status = Status[status]
        if status == Status.unknown:
            raise StrategyError(f"can not transition to {status}")
        elif status == self.status:
            step.skip("nothing to do")
            return  # nothing to do
        elif status == Status.off:
            self.target.deactivate(self.console)
            self.target.activate(self.power)
            self.power.off()
        elif status == Status.barebox:
            self.transition(Status.off)
            self.target.activate(self.console)
            # cycle power
            self.power.cycle()
            # interrupt barebox
            self.target.activate(self.barebox)
        elif status == Status.shell:
            # transition to barebox
            self.transition(Status.barebox)
            self.barebox.boot("")
            self.barebox.await_boot()
            self.target.activate(self.shell)
            self.shell.run("systemctl is-system-running --wait")
        else:
            raise StrategyError(
                f"no transition found from {self.status} to {status}"
            )
        self.status = status

    @step(args=['status'])
    def force(self, status):
        if not isinstance(status, Status):
            status = Status[status]
        self.target.activate(self.power)
        if status == Status.barebox:
            self.target.activate(self.barebox)
        elif status == Status.shell:
            self.target.activate(self.shell)
        else:
            raise StrategyError("can not force state {}".format(status))
        self.status = status
