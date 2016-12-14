import re

import attr
from pexpect import TIMEOUT
from ..protocol import CommandProtocol, ConsoleProtocol
from ..util import PtxExpect
from ..factory import target_factory
from .exception import NoDriverError, ExecutionError


@target_factory.reg_driver
@attr.s
class ShellDriver(CommandProtocol):
    """ShellDriver - Driver to execute commands on the shell"""
    target = attr.ib()
    prompt = attr.ib(default="", validator=attr.validators.instance_of(str))
    login_prompt = attr.ib(default="", validator=attr.validators.instance_of(str))

    def __attrs_post_init__(self):
        self.console = self.target.get_driver(ConsoleProtocol) #pylint: disable=no-member,attribute-defined-outside-init
        if not self.console:
            raise NoDriverError("Resource has no {} Driver".format(ConsoleProtocol))
        self.target.drivers.append(self) #pylint: disable=no-member
        self.expect = PtxExpect(self.console) #pylint: disable=attribute-defined-outside-init
        self.re_vt100 = re.compile('(\x1b\[|\x9b)[^@-_a-z]*[@-_a-z]|\x1b[@-_a-z]') #pylint: disable=attribute-defined-outside-init,anomalous-backslash-in-string
        self._status = 0 #pylint: disable=attribute-defined-outside-init
        self._check_prompt()
        self._inject_run()

    def run(self, cmd):
        """
        Runs the specified cmd on the shell and returns the output.

        Arguments:
        cmd - cmd to run on the shell
        """
        # FIXME: Handle pexpect Timeout
        cmp_command = "run {}".format(cmd)
        if self._status == 1:
            self.expect.sendline(cmp_command)
            self.expect.expect(self.prompt)
            # Remove VT100 Codes and split by newline
            data = self.re_vt100.sub('', self.expect.before.decode('utf-8'),
                                     count=1000000).split('\r\n')
            # Remove first element, the invoked cmd
            data.remove(cmp_command)
            del(data[-1])
            exitcode = int(data[-1])
            del(data[-1])
            return (data, exitcode)
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
        if res[1] != 0:
            raise ExecutionError(cmd)
        return res[0]

    def get_status(self):
        """Returns the status of the shell-driver.
        0 means not connected/found, 1 means shell
        """
        return self._status

    def _check_prompt(self):
        """
        Internal function to check if we have a valid prompt
        """
        self.expect.sendline("")
        try:
            self.expect.expect(self.prompt)
            self._status = 1
        except TIMEOUT:
            self._status = 0

    def _inject_run(self):
        self.expect.sendline('run() { cmd=$1; shift; ${cmd} $@; echo "$?"; }')
        self.expect.expect(self.prompt)
