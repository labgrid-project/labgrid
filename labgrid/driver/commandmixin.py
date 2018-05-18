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

    @Driver.check_active
    @step(args=['cmd', 'pattern'])
    def wait_for(self, cmd, pattern, timeout=30.0, sleepduration=1):
        timeout = Timeout(timeout)
        while not any(pattern in s for s in self.run_check(cmd)) and not timeout.expired:
            sleep(sleepduration)
        if timeout.expired:
            raise ExecutionError("Wait timeout expired")

    @Driver.check_active
    @step(args=['cmd', 'expected', 'tries', 'timeout', 'sleepduration'])
    def poll_until_success(self, cmd, *, expected=0, tries=None, timeout=30.0, sleepduration=1):
        timeout = Timeout(timeout)
        while not timeout.expired:
            _, _, exitcode = self.run(cmd, timeout=timeout.remaining)
            if exitcode == expected:
                return True
            sleep(sleepduration)
            if tries is not None:
                tries -= 1
                if tries < 1:
                    break
        return False

    def _run_check(self, cmd: str, *, timeout=30, codec: str = "utf-8",
                   decodeerrors: str = "strict"):
        """
        Internal function which runs the specified command on the shell and
        returns the output if successful, raises ExecutionError otherwise.

        Args:
            cmd (str): command to run on the shell

        Returns:
            List[str]: stdout of the executed command
        """
        stdout, stderr, exitcode = self._run(cmd, timeout=timeout, codec=codec,
                                             decodeerrors=decodeerrors)
        if exitcode != 0:
            raise ExecutionError(cmd, stdout, stderr)
        return stdout

    @Driver.check_active
    @step(args=['cmd'], result=True)
    def run_check(self, cmd: str, *, timeout=30, codec="utf-8", decodeerrors="strict"):
        """
        External run_check function, only available if the driver is active.
        Runs the supplied command and returns the stdout, raises an
        ExecutionError otherwise.

        Args:
            cmd (str): command to run on the shell

        Returns:
            List[str]: stdout of the executed command
        """
        return self._run_check(cmd, timeout=timeout, codec=codec, decodeerrors=decodeerrors)
