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
