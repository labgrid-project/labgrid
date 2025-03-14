def test_ssh_raw(target):
    """Simple test with SSHDriver directly executing a command on the DUT"""
    ssh_driver = target.get_driver('SSHDriver')
    stdout, stderr, returncode = ssh_driver.run('cat /proc/version')
    assert returncode == 0
    assert stdout
    assert not stderr


def test_ssh_command(target):
    """Simple test running through the command protocol abstraction"""
    command = target.get_driver('CommandProtocol')
    stdout, stderr, returncode = command.run('cat /proc/version')
    assert returncode == 0
    assert stdout
    assert not stderr
