from time import monotonic

from pytest import approx

from labgrid.protocol import CommandProtocol


def test_sleep(target):
    command = target.get_driver(CommandProtocol)

    # measure the round-trip-time
    timestamp = monotonic()
    stdout, stderr, returncode = command.run('true')
    elapsed_true = monotonic() - timestamp
    assert returncode == 0
    assert len(stdout) == 0
    assert len(stderr) == 0

    timestamp = monotonic()
    stdout, stderr, returncode = command.run('sleep 1')
    elapsed_sleep = monotonic() - timestamp
    assert returncode == 0
    assert len(stdout) == 0
    assert len(stderr) == 0

    assert elapsed_true < elapsed_sleep

    assert elapsed_sleep - elapsed_true == approx(1.0, abs=1e-2)
