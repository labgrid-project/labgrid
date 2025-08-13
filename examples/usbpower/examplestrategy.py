import enum

import attr

from labgrid.driver import BareboxDriver, ShellDriver, USBSDMuxDriver
from labgrid import step, target_factory
from labgrid.protocol import PowerProtocol
from labgrid.strategy import Strategy


@attr.s(eq=False)
class StrategyError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))


class Status(enum.Enum):
    unknown = 0
    barebox = 1
    shell = 2


@target_factory.reg_driver
@attr.s(eq=False)
class ExampleStrategy(Strategy):
    """ExampleStrategy - Strategy to for the usbpower labgrid example"""

    bindings = {
        "power": PowerProtocol,
        "sdmux": USBSDMuxDriver,
        "barebox": BareboxDriver,
        "shell": ShellDriver,
    }

    status = attr.ib(default=Status.unknown)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    @step(args=["status"])
    def transition(self, status, *, step):
        if not isinstance(status, Status):
            status = Status[status]
        if status == Status.unknown:
            raise StrategyError(f"can not transition to {status}")
        elif status == self.status:
            step.skip("nothing to do")
            return  # nothing to do
        elif status == Status.barebox:
            self.target.activate(self.power)
            self.target.activate(self.sdmux)
            # power off
            self.power.off()
            # configure sd-mux
            self.sdmux.set_mode("dut")
            # cycle power
            self.power.on()
            # interrupt barebox
            self.target.activate(self.barebox)
        elif status == Status.shell:
            # transition to barebox
            self.transition(Status.barebox)
            self.barebox.boot("")
            self.barebox.await_boot()
            self.target.activate(self.shell)
        else:
            raise StrategyError(f"no transition found from {self.status} to {status}")
        self.status = status
