import re

import pytest

from labgrid.driver import ExecutionError


def test_memory_mbw(command):
    """Test memcopy bandwidth"""
    try:
        command.run_check('which mbw')
    except ExecutionError:
        pytest.skip("mbw missing")

    result = command.run_check('mbw -qt0 8M')
    result = result[-1].strip()

    pattern = r"AVG\s+.*Copy:\s+(?P<bw>\S+)\s+MiB/s"
    bw, = map(float, re.fullmatch(pattern, result).groups())
    assert bw > 40  # > 40 MiB/second


def test_memory_memtester_short(command):
    """Test RAM for errors"""
    try:
        command.run_check('which memtester')
    except ExecutionError:
        pytest.skip("memtester missing")

    result = command.run_check('memtester 128k 1 | tail -n 1')
    result = result[-1].strip()

    assert result == "Done."
