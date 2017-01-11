# pylint: disable=no-member
import logging
import re
import shlex

import attr
from pexpect import TIMEOUT

from ..factory import target_factory
from ..protocol import CommandProtocol, ConsoleProtocol, LinuxBootProtocol
from ..step import step
from ..util import gen_marker
from .common import Driver
from .exception import ExecutionError


@target_factory.reg_driver
@attr.s
class BareboxDriver(Driver, CommandProtocol, LinuxBootProtocol):
    """BareboxDriver - Driver to control barebox via the console"""
    bindings = {"console": ConsoleProtocol, }
    prompt = attr.ib(default="", validator=attr.validators.instance_of(str))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.re_vt100 = re.compile(
            r'(\x1b\[|\x9b)[^@-_a-z]*[@-_a-z]|\x1b[@-_a-z]'
        )
        self.logger = logging.getLogger("{}:{}".format(self, self.target))
        self._status = 0

    def on_activate(self):
        self._check_prompt()
        if self._status == 0:
            self.await_prompt()

    @step("run")
    def run(self, cmd, *, step):
        """
        Runs the specified cmd on the shell and returns the output.

        Arguments:
        cmd - cmd to run on the shell
        """
        # FIXME: Handle pexpect Timeout
        marker = gen_marker()
        cmp_command = '''echo -o /cmd {}; echo "{}"; sh /cmd; echo "$?"; echo "{}";'''.format(
            shlex.quote(cmd),
            marker,
            marker,
        )
        if self._status == 1:
            self.console.sendline(cmp_command)
            _, before, _, _ = self.console.expect(self.prompt)
            # Remove VT100 Codes and split by newline
            data = self.re_vt100.sub(
                '', before.decode('utf-8'), count=1000000
            ).split('\r\n')
            self.logger.debug("Received Data: %s", data)
            # Remove first element, the invoked cmd
            data = data[data.index(marker) + 1:]
            data = data[:data.index(marker)]
            exitcode = int(data[-1])
            del data[-1]
            return (data, [], exitcode)
        else:
            return None

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
        """Returns the status of the barebox driver.
        0 means not connected/found, 1 means shell
        """
        return self._status

    def _check_prompt(self):
        """
        Internal function to check if we have a valid prompt
        """
        self.console.sendline("")
        try:
            self.console.expect(self.prompt, timeout=1)
            self._status = 1
        except TIMEOUT:
            self._status = 0

    def await_prompt(self):
        """Await autoboot line and stop it to get to the prompt"""
        self.console.expect(r"[\n]barebox 20\d+")
        index, _, _, _ = self.console.expect([self.prompt, "stop autoboot"])
        if index == 0:
            self._status = 1
        else:
            self._check_prompt()

    def await_boot(self):
        self.console.expect(r"Linux version \d")

    def boot(self, name):
        if name:
            self.console.sendline("boot -v {}".format(name))
        else:
            self.console.sendline("boot -v")
