def test_shell(command):
    stdout, stderr, returncode = command.run("cat /proc/version")
    assert returncode == 0
    assert stdout
    assert not stderr
    assert "Linux" in stdout[0]

    stdout, stderr, returncode = command.run("false")
    assert returncode != 0
    assert not stdout
    assert not stderr
