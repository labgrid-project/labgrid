import pytest


@pytest.fixture(scope="session")
def command(target):
    barebox = target.get_driver("CommandProtocol")
    target.activate(barebox)
    return barebox
