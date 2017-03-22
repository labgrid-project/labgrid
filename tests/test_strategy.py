import pytest

from labgrid.binding import BindingState
from labgrid.driver import BareboxDriver, UBootDriver, ShellDriver
from labgrid.driver.fake import FakeConsoleDriver, FakePowerDriver
from labgrid.protocol import (CommandProtocol, ConsoleProtocol,
                              LinuxBootProtocol)
from labgrid.strategy import Strategy, BareboxStrategy, UBootStrategy
from labgrid.exceptions import NoDriverFoundError


def test_create_barebox(target):
    console = FakeConsoleDriver(target)
    power = FakePowerDriver(target)
    barebox = BareboxDriver(target)
    shell = ShellDriver(target, prompt='root@dummy', login_prompt='login:', username='root')
    s = BareboxStrategy(target)

    assert isinstance(s, Strategy)
    assert target.get_driver(BareboxStrategy) is s
    assert target.get_driver(Strategy) is s

    assert s.state is BindingState.bound

def test_create_uboot(target):
    console = FakeConsoleDriver(target)
    power = FakePowerDriver(target)
    barebox = UBootDriver(target)
    shell = ShellDriver(target, prompt='root@dummy', login_prompt='login:', username='root')
    s = UBootStrategy(target)

    assert isinstance(s, Strategy)
    assert target.get_driver(UBootStrategy) is s
    assert target.get_driver(Strategy) is s

    assert s.state is BindingState.bound
