# pylint: disable=no-member
import logging
import re
import shlex
from time import sleep

import attr
from pexpect import TIMEOUT

from ..factory import target_factory
from ..protocol import CommandProtocol, ConsoleProtocol, LinuxBootProtocol
from ..step import step
from ..util import gen_marker, Timeout
from .common import Driver
from .commandmixin import CommandMixin
from .exception import ExecutionError


@target_factory.reg_driver
@attr.s(cmp=False)
class BareboxDriver(CommandMixin, Driver, CommandProtocol, LinuxBootProtocol):
    """BareboxDriver - Driver to control barebox via the console.
       BareboxDriver binds on top of a ConsoleProtocol.

    Args:
        prompt (str): The default Barebox Prompt
        startstring (str): string that indicates that Barebox is starting
        bootstring (str): string that indicates that the Kernel is booting
    """
    bindings = {"console": ConsoleProtocol, }
    prompt = attr.ib(default="", validator=attr.validators.instance_of(str))
    autoboot = attr.ib(default="stop autoboot", validator=attr.validators.instance_of(str))
    interrupt = attr.ib(default="\n", validator=attr.validators.instance_of(str))
    startstring = attr.ib(default=r"[\n]barebox 20\d+", validator=attr.validators.instance_of(str))
    bootstring = attr.ib(default="Linux version \d", validator=attr.validators.instance_of(str))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.re_vt100 = re.compile(
            r'(\x1b\[|\x9b)[^@-_a-z]*[@-_a-z]|\x1b[@-_a-z]'
        )
        self.logger = logging.getLogger("{}:{}".format(self, self.target))
        self._status = 0

    def on_activate(self):
        """Activate the BareboxDriver

        This function checks for a prompt and awaits it if not already active
        """
        self._check_prompt()
        if self._status == 0:
            self._await_prompt()

    def on_deactivate(self):
        """Deactivate the BareboxDriver

        Simply sets the internal status to 0
        """
        self._status = 0

    @Driver.check_active
    @step(args=['cmd'])
    def run(self, cmd: str, *, step, timeout: int = 30):
        """
        Runs the specified command on the shell and returns the output.

        Args:
            cmd (str): command to run on the shell
            timeout (int): optional, timeout in seconds

        Returns:
            Tuple[List[str],List[str], int]: if successful, None otherwise
        """
        # FIXME: Handle pexpect Timeout
        marker = gen_marker()
        # hide marker from expect
        hidden_marker = '"{}""{}"'.format(marker[:4], marker[4:])
        cmp_command = '''echo -o /cmd {}; echo {}; sh /cmd; echo {} $?;'''.format(
            shlex.quote(cmd), hidden_marker, hidden_marker,
        )
        if self._status == 1:
            self.console.sendline(cmp_command)
            _, _, match, _ = self.console.expect(r'{}(.*){}\s+(\d+)\s+.*{}'.format(
                marker, marker, self.prompt
            ), timeout=timeout)
            # Remove VT100 Codes and split by newline
            data = self.re_vt100.sub('', match.group(1).decode('utf-8')).split('\r\n')[1:-1]
            self.logger.debug("Received Data: %s", data)
            # Get exit code
            exitcode = int(match.group(2))
            return (data, [], exitcode)
        else:
            return None

    @Driver.check_active
    @step()
    def reset(self):
        """Reset the board via a CPU reset
        """
        self.status = 0
        self.console.sendline("reset")
        self._await_prompt()

    def get_status(self):
        """Retrieve status of the BareboxDriver
        0 means inactive, 1 means active.

        Returns:
            int: status of the driver
        """
        return self._status

    def _check_prompt(self):
        """
        Internal function to check if we have a valid prompt.
        It sets the internal _status to 1 or 0 based on the prompt detection.
        """
        self.console.sendline("")
        try:
            self.console.expect(self.prompt, timeout=1)
            self._status = 1
        except TIMEOUT:
            self._status = 0

    def _await_prompt(self):
        """Await autoboot line and stop it to get to the prompt"""
        self.console.expect(self.startstring)
        index, _, _, _ = self.console.expect([self.prompt, self.autoboot])
        if index == 0:
            self._status = 1
        else:
            self.console.write(self.interrupt.encode('ASCII'))
            self._check_prompt()

    @Driver.check_active
    def await_boot(self):
        """Wait for the initial Linux version string to verify we succesfully
        jumped into the kernel.
        """
        self.console.expect(self.bootstring)

    @Driver.check_active
    def boot(self, name: str):
        """Boot the default or a specific boot entry

        Args:
            name (str): name of the entry to boot"""
        if name:
            self.console.sendline("boot -v {}".format(name))
        else:
            self.console.sendline("boot -v")
