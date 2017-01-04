import pytest

from labgrid.util import Timeout


class TestTimeout:
    def test_create(self):
        t = Timeout()
        assert (isinstance(t, Timeout))
        t = Timeout(5.0)
        assert (isinstance(t, Timeout))
        with pytest.raises(TypeError):
            t = Timeout(10)
        with pytest.raises(ValueError):
            t = Timeout(-1.0)

    def test_expire(self, mocker):
        m = mocker.patch('time.monotonic')
        m.return_value = 0.0

        t = Timeout(5.0)
        assert not t.expired
        assert t.remaining == 5.0

        m.return_value += 3.0
        assert not t.expired
        assert t.remaining == 2.0

        m.return_value += 3.0
        assert t.expired
        assert t.remaining == 0.0
