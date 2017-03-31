import re

import pytest

from labgrid.driver import ExecutionError


def test_rt_cyclictest_short(command):
    """Test a basic cyclictest run"""
    try:
        command.run_check('which cyclictest')
    except ExecutionError:
        pytest.skip("cyclictest missing")

    result = command.run_check('cyclictest -SN -D 5 -q')
    result = result[-1].strip()

    pattern = r"Min:\s+(?P<min>\w+)\s+Act:\s+\w+\s+Avg:\s+(?P<avg>\w+)\s+Max:\s+(?P<max>\w+)"
    min, avg, max = map(int, re.search(pattern, result).groups())
    assert min <= avg <= max
    assert avg < 1e6  # avg < 1 milliseconds
    assert max < 10e6  # max < 10 milliseconds


def test_rt_hackbench_short(command):
    """Test a basic hackbench run"""
    try:
        command.run_check('which hackbench')
    except ExecutionError:
        pytest.skip("hackbench missing")

    result = command.run_check('hackbench -f 10')
    result = result[-1].strip()

    pattern = r"Time:\s+(?P<time>\w+)"
    time, = map(int, re.search(pattern, result).groups())
    assert time < 20  # max 20 seconds
