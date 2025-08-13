import pytest


@pytest.fixture(scope="function")
def bootloader(target, strategy, capsys):
    with capsys.disabled():
        strategy.transition("barebox")
    return target["CommandProtocol"]  # this will return the BareboxDriver


@pytest.fixture(scope="function")
def shell(target, strategy, capsys):
    with capsys.disabled():
        strategy.transition("shell")
    return target["CommandProtocol"]  # this will return the ShellDriver


def test_barebox(bootloader):
    stdout, stderr, returncode = bootloader.run("version")
    assert returncode == 0
    assert stdout
    assert not stderr
    assert "barebox" in "\n".join(stdout)


def test_shell(shell):
    stdout, stderr, returncode = shell.run("cat /proc/version")
    assert returncode == 0
    assert stdout
    assert not stderr
    assert "Linux" in stdout[0]


def test_barebox_2(bootloader):
    bootloader.run_check("true")
