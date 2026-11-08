"""Power/firmware/Linux transitions without a dependency on a particular init."""
from concurrent.futures import ThreadPoolExecutor
import enum
import time

import attr

from ..factory import target_factory
from ..step import step
from .common import Strategy, StrategyError, never_retry


class Status(enum.Enum):
    unknown = 0
    off = 1
    bootloader = 2
    shell = 3


@target_factory.reg_driver
@attr.s(eq=False)
class LinuxBootStrategy(Strategy):
    """Boot any LinuxBootProtocol firmware, or boot directly to a Linux shell.

    The optional bootloader binding supports CFE, CoLo, YAMON and U-Boot.
    No systemd-specific readiness command is required. Power-on runs concurrently
    with firmware activation, so even zero-delay firmware can be interrupted.
    """
    bindings = {
        'power': 'PowerProtocol',
        'console': 'ConsoleProtocol',
        'bootloader': {'LinuxBootProtocol', None},
        'shell': 'ShellDriver',
    }
    status = attr.ib(default=Status.unknown)
    bootstring = attr.ib(default=r'Linux version\s', validator=attr.validators.instance_of(str))
    boot_timeout = attr.ib(default=120, validator=attr.validators.instance_of(int))

    power_delay = attr.ib(default=2.0, validator=attr.validators.instance_of(float))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.power_delay < 0 or self.boot_timeout <= 0:
            raise ValueError('power_delay must be nonnegative and boot_timeout positive')

    def _power_on(self, activate):
        # Only the already-active power driver runs in the worker. Target
        # activation and console I/O remain on the calling thread.
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.power.on)
            try:
                activate()
            finally:
                # Propagate power failures and always join the worker.
                future.result()

    @never_retry
    @step(args=['status'])
    def transition(self, status):
        self._transition(status)

    def _transition(self, status):
        if not isinstance(status, Status):
            status = Status[status]
        if status == Status.unknown:
            raise StrategyError('Cannot transition to unknown')
        if status == self.status:
            return
        if status == Status.off:
            self.target.deactivate(self.console)
            self.target.activate(self.power)
            self.power.off()
        elif status == Status.bootloader:
            if self.bootloader is None:
                raise StrategyError('No bootloader configured')
            self._transition(Status.off)
            time.sleep(self.power_delay)
            self.target.activate(self.console)
            self._power_on(lambda: self.target.activate(self.bootloader))
        elif status == Status.shell:
            if self.bootloader is not None:
                self._transition(Status.bootloader)
                self.bootloader.boot('')
                self.bootloader.await_boot()
            else:
                self._transition(Status.off)
                time.sleep(self.power_delay)
                self.target.activate(self.console)
                self._power_on(lambda: self.console.expect(self.bootstring, timeout=self.boot_timeout))
            self.target.activate(self.shell)
            self.shell.run_check('true')
        else:
            raise StrategyError(f'Cannot transition to {status}')
        self.status = status

    @never_retry
    @step(args=['status'])
    def force(self, status):
        if not isinstance(status, Status):
            status = Status[status]
        if status == Status.off:
            self.target.deactivate(self.console)
            self.target.activate(self.power)
        elif status == Status.shell:
            self.target.activate(self.power)
            self.target.activate(self.shell)
        else:
            raise StrategyError(f'Cannot force {status}')
        self.status = status
