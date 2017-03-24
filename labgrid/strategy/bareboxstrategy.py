import enum

import attr

from ..driver import BareboxDriver, ShellDriver
from ..factory import target_factory
from ..protocol import PowerProtocol
from ..step import step
from .common import Strategy


@attr.s
class StrategyError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))


class Status(enum.Enum):
    unknown = 0
    barebox = 1
    shell = 2


@target_factory.reg_driver
@attr.s
class BareboxStrategy(Strategy):
    """BareboxStrategy - Strategy to switch to barebox or shell"""
    bindings = {
        "power": PowerProtocol,
        "barebox": BareboxDriver,
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
        elif status == Status.barebox:
            # cycle power
            self.target.activate(self.power)
            self.power.cycle()
            # interrupt barebox
            self.target.activate(self.barebox)
        elif status == Status.shell:
            # tansition to barebox
            self.transition(Status.barebox)
            self.barebox.boot("")
            self.barebox.await_boot()
            self.target.activate(self.shell)
        else:
            raise StrategyError(
                "no transition found from {} to {}".
                format(self.status, status)
            )
        self.status = status
