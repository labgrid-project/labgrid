import pytest


def test_watchdog(command):
    stdout, stderr, returncode = command.run('wd 1')
    if returncode == 127:
        pytest.skip("wd command not available")
    assert returncode == 0
    assert len(stderr) == 0
    assert len(stdout) == 0

    command.await_prompt()

    stdout = command.run_check('echo ${global.system.reset}')
    assert len(stdout) == 1
    assert stdout[0] == 'WDG'
