import pytest

from labgrid import Target
from labgrid.exceptions import NoDriverFoundError, NoResourceFoundError


class TestTarget:
    def test_instanziation(self):
        t = Target("name")
        assert (isinstance(t, Target))

    def test_get_resource(self, target):
        class a():
            pass

        target.resources.append(a())
        assert isinstance(target.get_resource(a), a)

    def test_get_driver(self, target):
        class a():
            pass

        target.drivers.append(a())
        assert isinstance(target.get_driver(a), a)

    def test_no_resource(self, target):
        with pytest.raises(NoResourceFoundError):
            target.get_resource(Target)

    def test_no_driver(self, target):
        with pytest.raises(NoDriverFoundError):
            target.get_driver(Target)
