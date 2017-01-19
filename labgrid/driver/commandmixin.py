from time import sleep

from ..util import Timeout
from ..step import step
from .exception import ExecutionError


class CommandMixin:
    """
    Console driver mixin to implement the read, write, expect and sendline methods. It uses
    the internal _read and _write methods. 
    """

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    @step(args=['cmd', 'pattern'])
    def wait_for(self, cmd, pattern, timeout=30.0, sleepduration=1):
        timeout = Timeout(timeout)
        while not any(pattern in s for s in self.run_check(cmd)) and not timeout.expired:
            sleep(sleepduration)
        if timeout.expired:
            raise ExecutionError("Wait timeout expired")
