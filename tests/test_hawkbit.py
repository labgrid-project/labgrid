import pytest

from labgrid.external import HawkbitTestClient


class TestHawkbitTestClient:
    def test_create(self):
        c = HawkbitTestClient('dummyhost', '12345', 'user', 'password')
        assert (isinstance(c, HawkbitTestClient))
