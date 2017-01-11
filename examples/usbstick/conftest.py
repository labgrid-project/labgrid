import pytest

from labgrid.protocol import CommandProtocol
from labgrid.driver import SSHDriver, ShellDriver
from labgrid.external import USBStick

@pytest.fixture(scope="session")
def stick(target):
    shell = target.get_driver(ShellDriver)
    target.activate(shell)
    ssh = target.get_driver(SSHDriver)
    target.activate(ssh)
    return USBStick(target,'/mnt/sd/','backing_store')
