def test_bootchooser(command):
    stdout, stderr, returncode = command.run('bootchooser -i')
    if returncode == 127:
        pytest.skip("bootchooser command not available")
    assert returncode == 0
    assert len(stderr) == 0
    assert stdout[0].startswith('Good targets')
    assert stdout[1] != 'none'
