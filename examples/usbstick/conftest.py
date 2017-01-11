import pytest

from labgrid.driver import ShellDriver, SSHDriver
from labgrid.external import USBStick
from labgrid.protocol import CommandProtocol


@pytest.fixture(scope="session")
def stick(target):
    shell = target.get_driver(ShellDriver)
    target.activate(shell)
    ssh = target.get_driver(SSHDriver)
    target.activate(ssh)
    return USBStick(target, '/mnt/sd/', 'backing_store')
