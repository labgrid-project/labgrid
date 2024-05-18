import enum
import sys
import time

import attr

from ..factory import target_factory
from .common import Strategy, StrategyError


class Status(enum.Enum):
    """States supported by this strategy:

        unknown: State is not known
        off: Power is off
        start: Board has started booting
        uboot: Board has stopped at the U-Boot prompt
        shell: Board has stopped at the Linux prompt
    """
    unknown, off, start, uboot, shell = range(5)


@target_factory.reg_driver
@attr.s(eq=False)
class UBootStrategy(Strategy):
    """UbootStrategy - Strategy to switch to uboot or shell"""
    bindings = {
        "power": "PowerProtocol",
        "console": "ConsoleProtocol",
        "uboot": "UBootDriver",
        "shell": "ShellDriver",
        "reset": {"ResetProtocol", None},
    }

    status = attr.ib(default=Status.unknown)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    def start(self):
        """Start U-Boot, by powering on / resetting the board"""
        self.target.activate(self.console)
        if self.reset:
            self.target.activate(self.reset)

            # Hold in reset across the power cycle, to avoid booting the
            # board twice
            self.reset.set_reset_enable(True)
        if self.reset != self.power:
            self.power.cycle()

        if self.reset:
            self.reset.set_reset_enable(False)

    def transition(self, status):
        if not isinstance(status, Status):
            status = Status[status]
        if status == Status.unknown:
            raise StrategyError(f"can not transition to {status}")
        elif status == self.status:
            return # nothing to do
        elif status == Status.off:
            self.target.deactivate(self.console)
            self.target.activate(self.power)
            self.power.off()
        elif status == Status.start:
            self.transition(Status.off)
            self.start()
        elif status == Status.uboot:
            self.transition(Status.start)
            start = time.time()
            # interrupt uboot
            self.target.activate(self.uboot)
            output = self.console.read_output()
            sys.stdout.buffer.write(output)
            duration = time.time() - start
            print(f'\n{{lab ready in {duration:.1f}s: {self.uboot.version}}}')
        elif status == Status.shell:
            # transition to uboot
            self.transition(Status.uboot)
            self.uboot.boot("")
            self.uboot.await_boot()
            self.target.activate(self.shell)
            self.shell.run("systemctl is-system-running --wait")
        else:
            raise StrategyError(f"no transition found from {self.status} to {status}")
        self.status = status

    def force(self, status):
        if not isinstance(status, Status):
            status = Status[status]
        if status == Status.off:
            self.target.activate(self.power)
        elif status == Status.uboot:
            self.target.activate(self.uboot)
        elif status == Status.shell:
            self.target.activate(self.shell)
        else:
            raise StrategyError("can not force state {}".format(status))
        self.status = status
