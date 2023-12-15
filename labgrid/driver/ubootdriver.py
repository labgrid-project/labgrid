"""The U-Boot Module contains the UBootDriver"""
import attr
from pexpect import TIMEOUT

from ..factory import target_factory
from ..protocol import CommandProtocol, ConsoleProtocol, LinuxBootProtocol
from ..util import gen_marker, Timeout, re_vt100
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
        autoboot (str): optional, string to search for to interrupt autoboot
        interrupt (str): optional, character to interrupt autoboot and go to prompt
        password_prompt (str): optional, string to detect the password prompt
        boot_expression (str): optional, deprecated
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
    boot_expression = attr.ib(default="", validator=attr.validators.instance_of(str))
    bootstring = attr.ib(default=r"Linux version \d", validator=attr.validators.instance_of(str))
    boot_command = attr.ib(default="run bootcmd", validator=attr.validators.instance_of(str))
    boot_commands = attr.ib(default=attr.Factory(dict), validator=attr.validators.instance_of(dict))
    login_timeout = attr.ib(default=30, validator=attr.validators.instance_of(int))
    boot_timeout = attr.ib(default=30, validator=attr.validators.instance_of(int))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._status = 0

        if self.boot_expression:
            import warnings
            warnings.warn("boot_expression is deprecated and will be ignored", DeprecationWarning)

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
            data = re_vt100.sub(
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
        self._status = 0
        self.console.sendline("reset")
        self._await_prompt()

    @step()
    def _await_prompt(self):
        """Await autoboot line and stop it to get to the prompt, optionally
        enter the password.
        """
        timeout = Timeout(float(self.login_timeout))

        # We call console.expect with a short timeout here to detect if the
        # console is idle, which would result in a timeout without any changes
        # to the before property. So we store the last before value we've seen.
        # Because pexpect keeps any read data in it's buffer when a timeout
        # occours, we can't lose any data this way.
        last_before = None

        expectations = [self.prompt, self.autoboot, self.password_prompt, TIMEOUT]
        while True:
            index, before, _, _ = self.console.expect(
                expectations,
                timeout=2
            )
            if index == 0:
                self._status = 1
                break

            elif index == 1:
                self.console.write(self.interrupt.encode('ASCII'))

            elif index == 2:
                if not self.password:
                    raise Exception("Password entry needed but no password set")
                self.console.sendline(self.password)

            elif index == 3:
                # expect hit a timeout while waiting for a match
                if before == last_before:
                    # we did not receive anything during the previous expect cycle
                    # let's assume the target is idle and we can safely issue a
                    # newline to check the state
                    self.console.sendline("")

                if timeout.expired:
                    raise TIMEOUT(
                        f"Timeout of {self.login_timeout} seconds exceeded during waiting for login"
                    )

            last_before = before

        if self.prompt:
            self._check_prompt()

        for command in self.init_commands:
            self._run_check(command)

    @Driver.check_active
    @step()
    def await_boot(self):
        """Wait for the initial Linux version string to verify we successfully
        jumped into the kernel.
        """
        self.console.expect(self.bootstring, timeout=self.boot_timeout)

    @Driver.check_active
    @step(args=['name'])
    def boot(self, name: str = ""):
        """Boot the default or a specific boot entry

        Args:
            name (str): name of the entry to boot"""
        if name:
            try:
                self.console.sendline(self.boot_commands[name])
            except KeyError as e:
                raise Exception(f"{name} not found in boot_commands") from e
        else:
            self.console.sendline(self.boot_command)
