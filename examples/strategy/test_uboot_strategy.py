import pytest
import logging

from labgrid.driver import UBootDriver, ShellDriver
from labgrid.protocol import CommandProtocol
from labgrid.strategy import UBootStrategy


@pytest.fixture()
def strategy(target):
    try:
        return target.get_driver(UBootStrategy)
    except:
        pytest.skip("strategy not found")


@pytest.fixture(scope="function")
def in_bootloader(strategy, capsys):
    with capsys.disabled():
        strategy.transition("uboot")


@pytest.fixture(scope="function")
def in_shell(strategy, capsys):
    with capsys.disabled():
        strategy.transition("shell")


def test_uboot(target, in_bootloader):
    #command = target.get_driver(CommandProtocol)
    command = target.get_driver(UBootDriver)

    stdout, stderr, returncode = command.run('version')
    assert returncode == 0
    assert len(stdout) > 0
    assert len(stderr) == 0
    assert 'U-Boot' in '\n'.join(stdout)


def test_shell(target, in_shell):
    #command = target.get_driver(CommandProtocol)
    command = target.get_driver(ShellDriver)
    stdout, stderr, returncode = command.run('cat /proc/version')
    assert returncode == 0
    assert len(stdout) > 0
    assert len(stderr) == 0
    assert 'Linux' in stdout[0]


def test_uboot_2(target, in_bootloader):
    command = target.get_driver(UBootDriver)

    stdout, stderr, returncode = command.run('version')
    assert returncode == 0
    assert len(stdout) > 0
    assert len(stderr) == 0
    assert 'U-Boot' in '\n'.join(stdout)
