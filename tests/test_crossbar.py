from importlib.util import find_spec

import pytest

if not find_spec('crossbar'):
    pytest.skip("crossbar not found")

def test_startup(crossbar):
    pass
