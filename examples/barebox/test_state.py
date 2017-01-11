import pytest


def test_state(command):
    stdout, stderr, returncode = command.run('state')
    if returncode == 127:
        pytest.skip("state command not available")
    assert returncode == 0
    assert len(stderr) == 0
    assert stdout[0] == 'registered state instances:'
    assert len(stdout) > 1
