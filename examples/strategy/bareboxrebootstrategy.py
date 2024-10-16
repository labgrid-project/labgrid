import enum

import attr

from labgrid import target_factory, step
from labgrid.driver import BareboxDriver, ShellDriver
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
class BareboxRebootStrategy(Strategy):
    """A Strategy to switch to barebox or shell and back via reboot

    In your env.yaml, simply instantiate the strategy without parameters, for example:

    .. code-block:: yaml
        targets:
            main:
                resources:
                  RawSerialPort:
                    port: "/dev/ttyUSB0"
                drivers:
                  ManualPowerDriver:
                    name: "example"
                  SerialDriver {}
                  BareboxDriver:
                    prompt: 'barebox@[^:]+:[^ ]+ '
                    bootstring: '\[[ .0-9]+\] '
                  ShellDriver:
                    prompt: 'root@\w+:[^ ]+ '
                    login_prompt: ' login: '
                    username: 'root'
                  BareboxRebootStrategy: {}
    """

    # pull in the according drivers into self.*
    bindings = {
        "power": PowerProtocol,
        "barebox": BareboxDriver,
        "shell": ShellDriver,
    }

    status = attr.ib(default=Status.unknown)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    @step(args=["new_status"])
    def transition(self, new_status, *, step):
        if not isinstance(new_status, Status):
            new_status = Status[new_status]

        if new_status == Status.unknown:
            raise StrategyError(f"can not transition to {new_status}")

        elif self.status == new_status:
            step.skip("nothing to do")
            return

        elif self.status == Status.unknown:
            # unknown state after initialization, cycle power
            self.target.activate(self.power)
            self.power.cycle()

            # we can then let the according driver do the rest to get us into a barebox or shell:
            if new_status == Status.barebox:
                self.target.activate(self.barebox)
            elif new_status == Status.shell:
                # (this assumes that barebox will autoboot to the shell after a timeout)
                self.target.activate(self.shell)

        elif self.status == Status.barebox and new_status == Status.shell:
            # in barebox: boot the default target and hope it will get us to a shell :->
            self.barebox.boot("")
            self.barebox.await_boot()
            self.target.activate(self.shell)

        elif self.status == Status.shell and new_status == Status.barebox:
            # in shell: we can simply reboot to get a barebox
            # make sure run() reads the shell prompt and returns
            self.shell.run("(sleep 1;reboot)&")
            self.target.activate(self.barebox)

        else:
            raise StrategyError(f"no transition found from {self.status} to {new_status}")

        self.status = new_status
