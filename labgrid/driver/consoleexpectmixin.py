import time
import pexpect

from ..util import PtxExpect, Timeout
from ..step import step
from .common import Driver


class ConsoleExpectMixin:
    """
    Console driver mixin to implement the read, write, expect and sendline methods. It uses
    the internal _read and _write methods.

    The class using the ConsoleExpectMixin must provide a logger and a txdelay attribute.
    """

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._expect = PtxExpect(self)

    @Driver.check_active
    @step(result=True, tag='console')
    def read(self, size=1, timeout=0.0, max_size=None):
        res = self._read(size=size, timeout=timeout, max_size=max_size)
        if max_size:
            self.logger.debug("Read %i bytes: %s, timeout %.2f, requested size %i, max size %i",
                              len(res), res, timeout, size, max_size)
        else:
            self.logger.debug("Read %i bytes: %s, timeout %.2f, requested size %i",
                              len(res), res, timeout, size)
        return res

    @Driver.check_active
    @step(args=['data'], tag='console')
    def write(self, data):
        if self.txdelay:
            self.logger.debug("Write %i bytes: %s (with %fs txdelay)",
                              len(data), data, self.txdelay)
            count = 0
            for i in range(len(data)):
                time.sleep(self.txdelay)
                count += self._write(data[i:i+1])
            return count

        self.logger.debug("Write %i bytes: %s", len(data), data)
        return self._write(data)

    @Driver.check_active
    def sendline(self, line):
        self._expect.sendline(line)

    @Driver.check_active
    def sendcontrol(self, char):
        self._expect.sendcontrol(char)

    @Driver.check_active
    @step(args=['pattern'], result=True)
    def expect(self, pattern, timeout=-1):
        index = self._expect.expect(pattern, timeout=timeout)
        return index, self._expect.before, self._expect.match, self._expect.after

    @Driver.check_active
    @step(args=['quiet_time'])
    def settle(self, quiet_time, timeout=120.0) -> bool:
        t = Timeout(timeout)
        while not t.expired:
            try:
                self.read(timeout=quiet_time)
            except pexpect.TIMEOUT:
                return True
        return False

    def resolve_conflicts(self, client):
        for other in self.clients:
            if other is client:
                continue
            self.target.deactivate(other)
