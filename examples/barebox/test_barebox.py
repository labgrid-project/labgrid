def test_barebox(command):
    stdout, stderr, returncode = command.run("version")
    assert returncode == 0
    assert stdout
    assert not stderr
    assert "barebox" in "\n".join(stdout)

    stdout, stderr, returncode = command.run("false")
    assert returncode == 1
    assert not stdout
    assert not stderr
