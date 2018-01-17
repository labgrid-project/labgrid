import pytest


@pytest.fixture(scope='session')
def info(target):
    shell = target.get_driver('ShellDriver')
    target.activate(shell)
    info = target.get_driver('InfoDriver')
    target.activate(info)
    return info
