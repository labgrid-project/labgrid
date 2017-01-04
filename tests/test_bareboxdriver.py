import attr
import pytest

from labgrid import Target
from labgrid.driver import BareboxDriver
from labgrid.protocol import (CommandProtocol, ConsoleProtocol,
                              LinuxBootProtocol)


@attr.s
class FakeConsoleDriver(ConsoleProtocol):
    target = attr.ib()

    def __attrs_post_init__(self):
        self.target.drivers.append(self)

    def read(self, *args):
        pass

    def write(self, *args):
        pass

    def open(self):
        pass

    def close(self):
        pass

    def fileno(self):
        pass


class TestBareboxDriver:
    def test_create(self):
        t = Target('dummy')
        cp = FakeConsoleDriver(t)
        d = BareboxDriver(t)
        assert (isinstance(d, BareboxDriver))
        assert (isinstance(d, CommandProtocol))
        assert (isinstance(d, LinuxBootProtocol))
