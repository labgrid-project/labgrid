import pytest


@pytest.fixture(scope="function")
def in_bootloader(strategy, capsys):
    with capsys.disabled():
        strategy.transition("barebox")


@pytest.fixture(scope="function")
def in_shell(strategy, capsys):
    with capsys.disabled():
        strategy.transition("shell")


def test_barebox(target, in_bootloader):
    # command = target['CommandProtocol']
    command = target["BareboxDriver"]

    stdout, stderr, returncode = command.run("version")
    assert returncode == 0
    assert stdout
    assert not stderr
    assert "barebox" in "\n".join(stdout)


def test_shell(target, in_shell):
    # command = target['CommandProtocol']
    command = target["ShellDriver"]
    stdout, stderr, returncode = command.run("cat /proc/version")
    assert returncode == 0
    assert stdout
    assert not stderr
    assert "Linux" in stdout[0]


def test_barebox_2(target, in_bootloader):
    # command = target['CommandProtocol']
    command = target["BareboxDriver"]

    command.run_check("true")
