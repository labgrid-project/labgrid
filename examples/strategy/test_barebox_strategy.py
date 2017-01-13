import pytest

from labgrid.driver import BareboxDriver, ShellDriver
from labgrid.protocol import CommandProtocol
from labgrid.strategy import BareboxStrategy


@pytest.fixture()
def strategy(target):
    try:
        return target.get_driver(BareboxStrategy)
    except NoDriverFoundError:
        pytest.skip("strategy not found")

@pytest.fixture(scope="function")
def in_bootloader(strategy, capsys):
    with capsys.disabled():
        strategy.transition("barebox")


@pytest.fixture(scope="function")
def in_shell(strategy, capsys):
    with capsys.disabled():
        strategy.transition("shell")


def test_barebox(target, in_bootloader):
    #command = target.get_driver(CommandProtocol)
    command = target.get_driver(BareboxDriver)

    stdout, stderr, returncode = command.run('version')
    assert returncode == 0
    assert len(stdout) > 0
    assert len(stderr) == 0
    assert 'barebox' in '\n'.join(stdout)


def test_shell(target, in_shell):
    #command = target.get_driver(CommandProtocol)
    command = target.get_driver(ShellDriver)
    stdout, stderr, returncode = command.run('cat /proc/version')
    assert returncode == 0
    assert len(stdout) > 0
    assert len(stderr) == 0
    assert 'Linux' in stdout[0]


def test_barebox_2(target, in_bootloader):
    #command = target.get_driver(CommandProtocol)
    command = target.get_driver(BareboxDriver)

    command.run_check('true')
