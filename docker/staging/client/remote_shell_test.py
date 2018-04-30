def test_shell(target):
    shell = target.get_driver('CommandProtocol')
    target.activate(shell)
    stdout, stderr, returncode = shell.run('uname -r')

    assert stdout
    print('Kernel {}'.format(stdout))
