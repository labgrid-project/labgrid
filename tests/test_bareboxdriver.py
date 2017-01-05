import attr
import pytest

from labgrid import Target
from labgrid.driver import BareboxDriver
from labgrid.driver.fake import FakeConsoleDriver
from labgrid.protocol import (CommandProtocol, ConsoleProtocol,
                              LinuxBootProtocol)


class TestBareboxDriver:
    def test_create(self):
        t = Target('dummy')
        cp = FakeConsoleDriver(t)
        d = BareboxDriver(t)
        assert (isinstance(d, BareboxDriver))
        assert (isinstance(d, CommandProtocol))
        assert (isinstance(d, LinuxBootProtocol))
