import attr

from ..factory import target_factory
from ..util import gen_marker
from ..step import step
from .common import Driver

from .ubootdriver import UBootDriver

@target_factory.reg_driver
@attr.s(cmp=False)
class SmallUBootDriver(UBootDriver):
    """
    SmallUBootDriver is meant as a driver for UBoot with only little
    functionality compared to standard a standard UBoot.
    Especially is copes with the following limitations:

    - The UBoot does not have a real password-prompt but can be activated by
      entering a "secret" after a message was displayed.
    - The command line is does not have a build-in echo command. Thus this
      driver uses 'Unknown Command' messages as marker before and after the
      output of a command.
    - Since there is no echo we can not return the exit code of the command.
      Commands will always return 0 unless the command was not found.

    This driver needs the following features activated in UBoot to work:

    - The UBoot must not have real password prompt. Instead it must be
      keyword activated.
      For example it should be activated by a dialog like the following:
      UBoot: "Autobooting in 1s..."
      Labgrid: "secret"
      UBoot: <switching to console>
    - The UBoot must be able to parse multiple commands in a single
      line separated by ";".
    - The UBoot must support the "bootm" command to boot from a
      memory location.

    This driver was created especially for the following devices:

    - TP-Link WR841 v11
    """

    boot_secret = attr.ib(default="a", validator=attr.validators.instance_of(str))

    @step()
    def _await_prompt(self):
        """
        Await autoboot_expression. If this line was read enter the 'secret' (or a
        single character) to interrupt normal boot.
        """

        # wait for boot expression. Afterwards enter secret
        self.console.expect(self.boot_expression)
        self.console.sendline(self.boot_secret)
        self._status = 1

        # wait until UBoot has reached it's prompt
        self.console.expect(self.prompt)

    @step(args=['cmd'], result=True)
    def _run(self, cmd):
        """
        If Uboot is in Command-Line mode: Run command cmd and return it's
        output.

        Arguments:
        cmd - Command to run
        """

        # Check if Uboot is in command line mode
        if self._status != 1:
            return None

        marker = gen_marker()

        # Create multi-part command like we would do for a normal uboot.
        # but since this simple uboot does not have an echo-command we will
        # handle it's error message as an echo-output.
        # additionally we are not able to get the command's return code and
        # will always return 0.
        cmp_command = """echo{}; {}; echo{}""".format(
            marker,
            cmd,
            marker
        )

        self.console.sendline(cmp_command)
        _, before, _, _ = self.console.expect(self.prompt)

        data = self.re_vt100.sub(
            '', before.decode('utf-8'), count=1000000
        ).replace("\r", "").split("\n")
        data = data[1:]
        data = data[data.index("Unknown command 'echo{}' - try 'help'".format(marker)) +1 :]
        data = data[:data.index("Unknown command 'echo{}' - try 'help'".format(marker))]
        if len(data) >= 1:
            if data[0].startswith("Unknown command '"):
                return (data, [], 1)
        return (data, [], 0)

    @Driver.check_active
    @step(args=['name'], result=True)
    def boot(self, name):
        """
        Boot the device from the given memory location using 'bootm'.

        Args:
            name (str): address to boot
        """
        self.console.sendline("bootm {}".format(name))
