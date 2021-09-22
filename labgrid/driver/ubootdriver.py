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
from .commandmixin import CommandMixin


@target_factory.reg_driver
@attr.s(eq=False)
class UBootDriver(CommandMixin, Driver, CommandProtocol, LinuxBootProtocol):
    """UBootDriver - Driver to control uboot via the console.
    UBootDriver binds on top of a ConsoleProtocol.

    Args:
        prompt (str): optional, U-Boot prompt
        password (str): optional, password to unlock U-Boot
        init_commands (tuple): optional, tuple of commands to run after unlock
        interrupt(str): optional, interrupt character to use to go to prompt
        password_prompt (str): optional, string to detect the password prompt
        boot_expression (str): optional, string to search for on U-Boot start
        bootstring (str): optional, string that indicates that the Kernel is booting
        boot_command (str): optional boot command to boot target
        login_timeout (int): optional, timeout for login prompt detection
        boot_timeout (int): optional, timeout for initial Linux Kernel version detection

    """
    bindings = {"console": ConsoleProtocol, }
    prompt = attr.ib(default="", validator=attr.validators.instance_of(str))
    autoboot = attr.ib(default="stop autoboot", validator=attr.validators.instance_of(str))
    password = attr.ib(default="", validator=attr.validators.instance_of(str))
    interrupt = attr.ib(default="\n", validator=attr.validators.instance_of(str))
    init_commands = attr.ib(default=attr.Factory(tuple), converter=tuple)
    password_prompt = attr.ib(default="enter Password:", validator=attr.validators.instance_of(str))
    boot_expression = attr.ib(default=r"U-Boot 20\d+", validator=attr.validators.instance_of(str))
    bootstring = attr.ib(default=r"Linux version \d", validator=attr.validators.instance_of(str))
    boot_command = attr.ib(default="run bootcmd", validator=attr.validators.instance_of(str))
    login_timeout = attr.ib(default=30, validator=attr.validators.instance_of(int))
    boot_timeout = attr.ib(default=30, validator=attr.validators.instance_of(int))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.re_vt100 = re.compile(
            r'(\x1b\[|\x9b)[^@-_a-z]*[@-_a-z]|\x1b[@-_a-z]'
        )
        self.logger = logging.getLogger(f"{self}:{self.target}")
        self._status = 0

    def on_activate(self):
        """Activate the UBootDriver

        This function checks for a prompt and awaits it if not already active
        """
        if self._status == 0:
            self._await_prompt()

    def on_deactivate(self):
        """Deactivate the UBootDriver

        Simply sets the internal status to 0
        """
        self._status = 0

    def _run(self, cmd: str, *, timeout: int = 30, codec: str = "utf-8", decodeerrors: str = "strict"):  # pylint: disable=unused-argument,line-too-long
        # TODO: use codec, decodeerrors
        # TODO: Shell Escaping for the U-Boot Shell
        marker = gen_marker()
        cmp_command = f"""echo '{marker[:4]}''{marker[4:]}'; {cmd}; echo "$?"; echo '{marker[:4]}''{marker[4:]}';"""  # pylint: disable=line-too-long
        if self._status == 1:
            self.console.sendline(cmp_command)
            _, before, _, _ = self.console.expect(self.prompt, timeout=timeout)
            # Remove VT100 Codes and split by newline
            data = self.re_vt100.sub(
                '', before.decode('utf-8'), count=1000000
            ).replace("\r", "").split("\n")
            self.logger.debug("Received Data: %s", data)
            # Remove first element, the invoked cmd
            data = data[data.index(marker) + 1:]
            data = data[:data.index(marker)]
            exitcode = int(data[-1])
            del data[-1]
            return (data, [], exitcode)

        return None

    @Driver.check_active
    @step(args=['cmd'], result=True)
    def run(self, cmd, timeout=30):
        """
        Runs the specified command on the shell and returns the output.

        Args:
            cmd (str): command to run on the shell
            timeout (int): optional, how long to wait for completion

        Returns:
            Tuple[List[str],List[str], int]: if successful, None otherwise
        """
        return self._run(cmd, timeout=timeout)

    def get_status(self):
        """Retrieve status of the UBootDriver.
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
        marker = gen_marker()
        # hide marker from expect
        self.console.sendline(f"echo '{marker[:4]}''{marker[4:]}'")
        try:
            self.console.expect(f"{marker}", timeout=2)
            self.console.expect(self.prompt, timeout=1)
            self._status = 1
        except TIMEOUT:
            self._status = 0
            raise

    @Driver.check_active
    @step()
    def reset(self):
        """Reset the board via a CPU reset
        """
        self.status = 0
        self.send("reset\n")
        self.await_prompt()

    @step()
    def _await_prompt(self):
        """Await autoboot line and stop it to get to the prompt, optionally
        enter the password.
        """
        self.console.expect(self.boot_expression, timeout=self.login_timeout)
        while True:
            index, _, _, _ = self.console.expect(
                [self.prompt, self.autoboot, self.password_prompt]
            )
            if index == 0:
                self._status = 1
                break

            elif index == 1:
                self.console.write(self.interrupt.encode('ASCII'))

            elif index == 2:
                if self.password:
                    self.console.sendline(self.password)
                else:
                    raise Exception("Password entry needed but no password set")

        if self.prompt:
            self._check_prompt()

        for command in self.init_commands:  #pylint: disable=not-an-iterable
            self._run_check(command)

    @Driver.check_active
    @step()
    def await_boot(self):
        """Wait for the initial Linux version string to verify we succesfully
        jumped into the kernel.
        """
        self.console.expect(self.bootstring, timeout=self.boot_timeout)

    @Driver.check_active
    @step(args=['name'])
    def boot(self, name):
        """Boot the default or a specific boot entry

        Args:
            name (str): name of the entry to boot"""
        if name:
            self.console.sendline(f"boot -v {name}")
        else:
            self.console.sendline(self.boot_command)
