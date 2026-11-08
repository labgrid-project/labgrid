from threading import Event
from unittest.mock import Mock

import pytest

from labgrid import Target
from labgrid.driver import CFEDriver, ShellDriver
from labgrid.driver.fake import FakeConsoleDriver, FakePowerDriver
from labgrid.strategy import LinuxBootStrategy, StrategyError


@pytest.fixture(params=[True, False])
def setup_strategy(request, monkeypatch):
    target = Target('test')
    power = FakePowerDriver(target, 'power')
    console = FakeConsoleDriver(target, 'console')
    if request.param:
        CFEDriver(target, 'firmware', boot_command='boot')
    ShellDriver(target, 'shell', prompt='# ', login_prompt='login:', username='root')
    strategy = LinuxBootStrategy(target, 'strategy', power_delay=0.0)
    # Preserve real bindings but don't connect to hardware in these transition tests.
    monkeypatch.setattr(target, 'activate', Mock())
    monkeypatch.setattr(target, 'deactivate', Mock())
    for driver in target.drivers:
        for name in ('on', 'off', 'boot', 'await_boot', 'run_check', 'expect'):
            if hasattr(driver, name):
                monkeypatch.setattr(driver, name, Mock())
    return target, strategy, power, console


def test_shell(setup_strategy):
    target, strategy, power, console = setup_strategy
    strategy.transition('shell')
    assert strategy.status.name == 'shell'
    power.off.assert_called_once()
    power.on.assert_called_once()
    strategy.shell.run_check.assert_called_once_with('true')
    if strategy.bootloader:
        strategy.bootloader.boot.assert_called_once_with('')
        strategy.bootloader.await_boot.assert_called_once()
    else:
        console.expect.assert_called_once_with(r'Linux version\s', timeout=120)
    strategy.transition('shell')
    power.on.assert_called_once()
    strategy.transition('off')
    target.deactivate.assert_called_with(console)


def test_power_overlaps_console(setup_strategy):
    target, strategy, power, console = setup_strategy
    powered = Event()
    listening = Event()

    def power_on():
        powered.set()
        assert listening.wait(2)

    def activate(driver):
        if driver is strategy.bootloader:
            assert powered.wait(2)
            listening.set()

    power.on.side_effect = power_on
    target.activate.side_effect = activate
    console.expect.side_effect = lambda *args, **kwargs: listening.set()
    strategy.transition('shell')
    assert listening.is_set()


def test_power_failure_breaks_strategy(setup_strategy):
    _, strategy, power, _ = setup_strategy
    power.on.side_effect = RuntimeError('power failed')
    with pytest.raises(StrategyError):
        strategy.transition('shell')
    assert isinstance(strategy.broken, RuntimeError)
    with pytest.raises(StrategyError):
        strategy.transition('shell')


def test_missing_bootloader(setup_strategy):
    _, strategy, _, _ = setup_strategy
    if strategy.bootloader is None:
        with pytest.raises(StrategyError):
            strategy.transition('bootloader')
