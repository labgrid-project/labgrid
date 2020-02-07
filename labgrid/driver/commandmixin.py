from time import sleep

from ..util import Timeout
from ..step import step
from .common import Driver
from .exception import ExecutionError


class CommandMixin:
    """
    CommandMixin implementing common functions for drivers which support the CommandProtocol
    """

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.decodeerrors = 'strict'

    @Driver.check_active
    @step(args=['command', 'pattern'])
    def wait_for(self, command: str, pattern: str, *, timeout: int = 30, sleepduration: int = 1):
        """
        Wait until the pattern is detected in the output of command. Raises
        ExecutionError when the timeout expires.

        Args:
            command (str): command to run on the shell
            pattern (str): pattern as a string to look for in the output
            timeout (int): timeout for the pattern detection
            sleepduration (int): sleep time between the runs of the commands
        """
        timeout = Timeout(float(timeout))
        while not any(pattern in s for s in self.run_check(command)) and not timeout.expired:
            sleep(sleepduration)
        if timeout.expired:
            raise ExecutionError("Wait timeout expired")

    @Driver.check_active
    @step(args=['command', 'expected', 'tries', 'timeout', 'sleepduration'])
    def poll_until_success(self, command: str, *, expected: int = 0, tries: int = None,
                           timeout: int = 30, sleepduration: int = 1):
        """
        Poll a command until a specific exit code is detected.
        Takes a timeout and the number of tries to run the command.
        The sleepduration argument sets the duration between runs of the commands.

        Args:
            command (str): command to run on the shell
            expected (int): exitcode to detect
            tries (int): number of tries, can be None for infinite tries
            timeout (float): timeout for the exitcode detection
            sleepduration (int): sleep time between the runs of the commands

        Returns:
            bool: whether the command finally executed sucessfully
        """
        timeout = Timeout(float(timeout))
        while not timeout.expired:
            _, _, exitcode = self.run(command, timeout=timeout.remaining)
            if exitcode == expected:
                return True
            sleep(sleepduration)
            if tries is not None:
                tries -= 1
                if tries < 1:
                    break
        return False

    def _run_check(self, command: str, *, timeout: int = 30):
        """
        Internal function which runs the specified command on the shell and
        returns the output if successful, raises ExecutionError otherwise.

        Args:
            command (str): command to run on the shell

        Returns:
            List[str]: stdout of the executed command
        """
        stdout, stderr, exitcode = self._run(command, timeout=timeout)
        if exitcode != 0:
            raise ExecutionError(command, stdout, stderr)
        return stdout

    @Driver.check_active
    @step(args=['command'], result=True)
    def run_check(self, command: str, *, timeout: int = 30):
        """
        External run_check function, only available if the driver is active.
        Runs the supplied command and returns the stdout, raises an
        ExecutionError otherwise.

        Args:
            command (str): command to run on the shell

        Returns:
            List[str]: stdout of the executed command
        """
        return self._run_check(command, timeout=timeout)
