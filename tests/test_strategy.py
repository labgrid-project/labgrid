from labgrid.binding import BindingState
from labgrid.driver import BareboxDriver, UBootDriver, ShellDriver
from labgrid.driver.fake import FakeConsoleDriver, FakePowerDriver
from labgrid.strategy import Strategy, BareboxStrategy, UBootStrategy


def test_create_barebox(target):
    console = FakeConsoleDriver(target, "console")
    power = FakePowerDriver(target, "power")
    barebox = BareboxDriver(target, "barebox")
    shell = ShellDriver(target, "shell", prompt='root@dummy', login_prompt='login:', username='root')
    s = BareboxStrategy(target, "strategy")

    assert isinstance(s, Strategy)
    assert target.get_driver(BareboxStrategy) is s
    assert target.get_driver(Strategy) is s

    assert s.state is BindingState.bound

def test_create_uboot(target):
    console = FakeConsoleDriver(target, "console")
    power = FakePowerDriver(target, "power")
    barebox = UBootDriver(target, "uboot")
    shell = ShellDriver(target, "shell", prompt='root@dummy', login_prompt='login:', username='root')
    s = UBootStrategy(target, "strategy")

    assert isinstance(s, Strategy)
    assert target.get_driver(UBootStrategy) is s
    assert target.get_driver(Strategy) is s

    assert s.state is BindingState.bound
