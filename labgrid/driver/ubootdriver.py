# pylint: disable=no-member
"""The U-Boot Module contains the UBootDriver"""
import logging
import re

import attr
from pexpect import TIMEOUT

from ..factory import target_factory
from ..protocol import CommandProtocol, ConsoleProtocol, LinuxBootProtocol
from ..util import gen_marker
from ..step import step
from .common import Driver
from .exception import ExecutionError


@target_factory.reg_driver
@attr.s
class UBootDriver(Driver, CommandProtocol, LinuxBootProtocol):
    """UBootDriver - Driver to control uboot via the console"""
    bindings = {"console": ConsoleProtocol, }
    prompt = attr.ib(default="", validator=attr.validators.instance_of(str))
    password = attr.ib(default="", validator=attr.validators.instance_of(str))
    init_commands = attr.ib(default=attr.Factory(tuple), convert=tuple)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.re_vt100 = re.compile(
            r'(\x1b\[|\x9b)[^@-_a-z]*[@-_a-z]|\x1b[@-_a-z]'
        )
        self.logger = logging.getLogger("{}:{}".format(self, self.target))
        self._status = 0

    def on_activate(self):
        if self._status == 0:
            self.await_prompt()

    def on_deactivate(self):
        self._status = 0

    @step(args=['cmd'], result=True)
    def run(self, cmd):
        """
        Runs the specified cmd on the shell and returns the output.

        Arguments:
        cmd - cmd to run on the shell
        """
        # FIXME: Handle pexpect Timeout
        # TODO: Shell Escaping for the U-Boot Shell
        marker = gen_marker()
        cmp_command = """echo '{}''{}'; {}; echo "$?"; echo '{}''{}';""".format(
            marker[:4],
            marker[4:],
            cmd,
            marker[:4],
            marker[4:],
        )
        if self._status == 1:
            self.console.sendline(cmp_command)
            _, before, _, _ = self.console.expect(self.prompt)
            # Remove VT100 Codes and split by newline
            data = self.re_vt100.sub(
                '', before.decode('utf-8'), count=1000000
            ).replace("\r","").split("\n")
            self.logger.debug("Received Data: %s", data)
            # Remove first element, the invoked cmd
            data = data[data.index(marker) + 1:]
            data = data[:data.index(marker)]
            exitcode = int(data[-1])
            del data[-1]
            return (data, [], exitcode)
        else:
            return None

    @step(args=['cmd'], result=True)
    def run_check(self, cmd):
        """
        Runs the specified cmd on the shell and returns the output if successful,
        raises ExecutionError otherwise.

        Arguments:
        cmd - cmd to run on the shell
        """
        res = self.run(cmd)
        if res[2] != 0:
            raise ExecutionError(cmd)
        return res[0]

    def get_status(self):
        """Returns the status of the uboot driver.
        0 means not connected/found, 1 means shell
        """
        return self._status

    def _check_prompt(self):
        """
        Internal function to check if we have a valid prompt
        """
        marker = gen_marker()
        # hide marker from expect
        self.console.sendline("echo '{}''{}'".format(marker[:4], marker[4:]))
        try:
            self.console.expect("{}".format(marker), timeout=2)
            self.console.expect(self.prompt, timeout=1)
            self._status = 1
        except TIMEOUT:
            self._status = 0
            raise

    @step()
    def await_prompt(self):
        """Await autoboot line and stop it to get to the prompt"""
        self.console.expect(r"U-Boot 20\d+")
        index, _, _, _ = self.console.expect(
            [self.prompt, "stop autoboot", "enter Password:"]
        )
        if index == 0:
            self._status = 1
        elif index == 2:
            if self.password:
                self.console.sendline(self.password)
                self._check_prompt()
            else:
                raise Exception("Password entry needed but no password set")
        else:
            self._check_prompt()
        for command in self.init_commands:  #pylint: disable=not-an-iterable
            self.run_check(command)

    @step()
    def await_boot(self):
        """Wait for boot line of the linux kernel"""
        self.console.expect(r"Linux version \d")

    @step(args=['name'])
    def boot(self, name):
        if name:
            self.console.sendline("boot -v {}".format(name))
        else:
            self.console.sendline("run bootcmd")
