import pytest

from labgrid.protocol import InfoProtocol


@pytest.fixture(scope='session')
def info(target):
    shell = target.get_driver(InfoProtocol)
    target.activate(shell)
    return shell
