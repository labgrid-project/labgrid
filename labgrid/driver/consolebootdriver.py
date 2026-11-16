"""Shared console handling for firmware without shell command status markers."""
import re

import attr
from pexpect import TIMEOUT

from ..protocol import ConsoleProtocol, LinuxBootProtocol
from ..step import step
from ..util import Timeout
from .common import Driver
from .exception import ExecutionError


@attr.s(eq=False)
class ConsoleBootDriver(Driver, LinuxBootProtocol):
    """Base for prompt-oriented firmware with no portable exit status command.

    Commands are accepted only after their expected output and a fresh prompt.
    This deliberately does not implement CommandProtocol: a prompt alone cannot
    prove command success. Use a success expression for transfers.
    """
    bindings = {"console": ConsoleProtocol}
    prompt = attr.ib(default='', validator=attr.validators.instance_of(str))
    interrupt = attr.ib(default='\x03', validator=attr.validators.instance_of(str))
    autoboot = attr.ib(default='', validator=attr.validators.instance_of(str))
    interrupt_interval = attr.ib(default=0.25, validator=attr.validators.instance_of(float))
    settle_time = attr.ib(default=0.0, validator=attr.validators.instance_of(float))
    login_timeout = attr.ib(default=60, validator=attr.validators.instance_of(int))
    boot_timeout = attr.ib(default=120, validator=attr.validators.instance_of(int))
    bootstring = attr.ib(default=r'Linux version\s', validator=attr.validators.instance_of(str))
    boot_command = attr.ib(default='', validator=attr.validators.instance_of(str))
    boot_commands = attr.ib(factory=dict, validator=attr.validators.instance_of(dict))
    init_commands = attr.ib(factory=tuple, converter=tuple)
    reset_command = attr.ib(default='', validator=attr.validators.instance_of(str))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if not self.prompt:
            raise ValueError('A nonempty firmware prompt is required')
        if self.interrupt_interval <= 0 or self.login_timeout <= 0 or self.boot_timeout <= 0:
            raise ValueError('Firmware timeouts and interrupt interval must be positive')
        if self.settle_time < 0:
            raise ValueError('settle_time must be nonnegative')
        self._ready = False

    def on_activate(self):
        self._await_prompt()
        for command in self.init_commands:
            if isinstance(command, str):
                self._execute(command)
            else:
                self._execute(command['command'], expect=command.get('expect'),
                              timeout=command.get('timeout', 30))

    def on_deactivate(self):
        self._ready = False

    @step()
    def _await_prompt(self):
        deadline = Timeout(float(self.login_timeout))
        if self.autoboot:
            index, _, _, _ = self.console.expect([self.prompt, self.autoboot],
                                                 timeout=deadline.remaining)
            if index == 1:
                self.console.write(self.interrupt.encode('ascii'))
                self.console.expect(self.prompt, timeout=deadline.remaining)
        else:
            while True:
                if deadline.expired:
                    raise TIMEOUT('Timed out waiting for firmware prompt')
                # Send before expecting: some boards have a zero-second boot delay.
                if self.interrupt:
                    self.console.write(self.interrupt.encode('ascii'))
                index, _, _, _ = self.console.expect(
                    [self.prompt, TIMEOUT], timeout=min(self.interrupt_interval, deadline.remaining))
                if index == 0:
                    break
        if self.settle_time:
            if not self.console.settle(self.settle_time, timeout=deadline.remaining):
                raise TIMEOUT('Firmware console did not settle')
            self.console.sendline('')
            self.console.expect(self.prompt, timeout=deadline.remaining)
        self._ready = True

    def _execute(self, command, *, expect=None, timeout=30):
        self.console.sendline(command)
        # Consume the echo separately, so it cannot satisfy the success pattern.
        self.console.expect(re.escape(command), timeout=timeout)
        _, before, _, after = self.console.expect(self.prompt, timeout=timeout)
        if expect is not None and not re.search(expect.encode(), before + after):
            raise ExecutionError(f'Firmware command did not produce expected output: {command}')
        return before.decode('utf-8', errors='replace').replace('\r', '').strip()

    @Driver.check_active
    @step(args=['command'], result=True)
    def run_command(self, command, *, expect=None, timeout=30):
        return self._execute(command, expect=expect, timeout=timeout)

    @Driver.check_active
    @step(args=['name'])
    def boot(self, name=''):
        command = self.boot_commands[name] if name else self.boot_command
        if not command:
            raise ExecutionError('No firmware boot command configured')
        self.console.sendline(command)
        self._ready = False

    @Driver.check_active
    @step()
    def await_boot(self):
        self.console.expect(self.bootstring, timeout=self.boot_timeout)

    @Driver.check_active
    @step()
    def reset(self):
        if not self.reset_command:
            raise ExecutionError('No firmware reset command configured; use power cycling')
        self._ready = False
        self.console.sendline(self.reset_command)
        self._await_prompt()
