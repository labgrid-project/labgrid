import re

import pytest

from labgrid.driver import ExecutionError
from labgrid.protocol import CommandProtocol


def test_memory_mbw(target):
    """Test memcopy bandwidth"""
    command = target.get_driver(CommandProtocol)
    try:
        command.run_check('which mbw')
    except ExecutionError:
        pytest.skip("mbw missing")

    result = command.run_check('mbw -qt0 8M')
    result = result[-1].strip()

    pattern = r"AVG\s+.*Copy:\s+(?P<bw>\S+)\s+MiB/s"
    bw, = map(float, re.fullmatch(pattern, result).groups())
    assert bw > 40  # > 40 MiB/second


def test_memory_memtester_short(target):
    """Test RAM for errors"""
    command = target.get_driver(CommandProtocol)
    try:
        command.run_check('which memtester')
    except ExecutionError:
        pytest.skip("memtester missing")

    result = command.run_check('memtester 1M 1')
    result = result[-1].strip()

    assert result == "Done."
