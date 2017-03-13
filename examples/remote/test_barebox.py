from labgrid.protocol import CommandProtocol


def test_target(target):
    barebox = target.get_driver(CommandProtocol)
    target.activate(barebox)

    stdout, stderr, returncode = barebox.run('version')
    assert returncode == 0
    assert len(stdout) > 0
    assert len(stderr) == 0
    assert 'barebox' in '\n'.join(stdout)

    stdout, stderr, returncode = barebox.run('false')
    assert returncode == 1
    assert len(stdout) == 0
    assert len(stderr) == 0
