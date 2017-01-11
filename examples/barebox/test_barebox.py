def test_barebox(command):
    stdout, stderr, returncode = command.run('version')
    assert returncode == 0
    assert len(stdout) > 0
    assert len(stderr) == 0
    assert 'barebox' in '\n'.join(stdout)

    stdout, stderr, returncode = command.run('false')
    assert returncode == 1
    assert len(stdout) == 0
    assert len(stderr) == 0
