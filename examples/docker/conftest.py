import pytest


@pytest.fixture(scope="session")
def command(target):
    strategy = target.get_driver("DockerStrategy")
    strategy.transition("accessible")
    shell = target.get_driver("CommandProtocol")
    return shell
