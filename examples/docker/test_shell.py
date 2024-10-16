def test_shell(command):
    stdout, stderr, returncode = command.run("cat /proc/version")
    assert returncode == 0
    assert len(stdout) > 0
    assert len(stderr) == 0
    assert "Linux" in stdout[0]

    stdout, stderr, returncode = command.run("false")
    assert returncode != 0
    assert len(stdout) == 0
    assert len(stderr) == 0
