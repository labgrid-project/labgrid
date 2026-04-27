def test_ssh(target):
    """Simple test with SSHDriver directly executing a command on the DUT"""
    ssh_driver = target.get_driver("SSHDriver")
    stdout = ssh_driver.run_check("cat /proc/version")
    assert stdout
