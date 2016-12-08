import re

import attr
import pexpect.fdpexpect
from pexpect import TIMEOUT
from ..protocol import CommandProtocol
from .serialdriver import SerialDriver
from .exception import NoDriverException

@attr.s
class ShellDriver(CommandProtocol):
    """ShellDriver - Driver to execute commands on the shell"""
    target = attr.ib()
    prompt = attr.ib()
    login_prompt = attr.ib(default="")
    status = attr.ib(default=0)

    def __attrs_post_init__(self):
        # FIXME: Hard coded for only one driver, should find the correct one in order
        self.driver = self.target.get_driver(SerialDriver) #pylint: disable=no-member,attribute-defined-outside-init
        if not self.driver:
            raise NoDriverException("Resource has no {} Driver".format(SerialDriver))
        self.target.drivers.append(self) #pylint: disable=no-member
        self.expect = pexpect.fdpexpect.fdspawn(self.driver.fileno(),logfile=open('expect.log','bw')) #pylint: disable=attribute-defined-outside-init
        self._check_prompt()
        self.re_vt100 = re.compile('(\x1b\[|\x9b)[^@-_a-z]*[@-_a-z]|\x1b[@-_a-z]') #pylint: disable=attribute-defined-outside-init,anomalous-backslash-in-string

    def run(self, cmd):
        """
        Runs the specified cmd on the shell and returns the output.

        Arguments:
        cmd - cmd to run on the shell
        """
        if self.status == 1:
            self.expect.sendline("{}".format(cmd))
            self.expect.expect(self.prompt)
            # Remove VT100 Codes and split by newline
            data = self.re_vt100.sub('', self.expect.before.decode('utf-8'), count=1000000).split('\r\n')
            # Remove first element, the invoked cmd
            data.remove(cmd)
            return data
        else:
            return None

    def get_status(self):
        pass

    def _check_prompt(self):
        """
        Internal function to check if we have a valid prompt
        """
        self.expect.sendline("")
        try:
            self.expect.expect(self.prompt)
            self.status = 1
        except TIMEOUT:
            self.status = 0
