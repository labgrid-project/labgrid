import pytest

from labgrid.protocol import CommandProtocol, PowerProtocol


@pytest.fixture()
def in_bootloader(target, capsys):
    power = target.get_driver(PowerProtocol)
    command = target.get_driver(CommandProtocol)
    with capsys.disabled():
        power.cycle()
    command.await_prompt()


def test_watchdog(target, in_bootloader):
    command = target.get_driver(CommandProtocol)

    stdout, stderr, returncode = command.run('wd 1')
    if returncode == 127:
        pytest.skip("wd command not available")
    assert returncode == 0
    assert len(stderr) == 0
    assert len(stdout) == 0

    command.await_prompt()

    stdout, stderr, returncode = command.run('echo ${global.system.reset}')
    assert returncode == 0
    assert len(stderr) == 0
    assert len(stdout) == 1
    assert stdout[0] == 'WDG'
