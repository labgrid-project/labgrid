def test_shell(target):
    ssh_driver = target.get_driver('SSHDriver')
    target.activate(ssh_driver)

    stdout, stderr, returncode = ssh_driver.run('uname -r')

    assert stdout
    print(f'Kernel {stdout}')
