import pytest

from labgrid.external import USBStick


@pytest.fixture(scope="session")
def stick(target):
    shell = target.get_driver('ShellDriver')
    target.activate(shell)
    ssh = target.get_driver('SSHDriver')
    target.activate(ssh)
    u = USBStick(target, None, '/home/',)
    u.upload_image("backing_store")
    u.switch_image("backing_store")
    return u
