import pytest

from labgrid import Target
from labgrid.exceptions import NoDriverFoundError, NoResourceFoundError



# test basic construction
def test_instanziation():
    t = Target("name")
    assert (isinstance(t, Target))


def test_get_resource(target):
    class a():
        pass

    target.resources.append(a())
    assert isinstance(target.get_resource(a), a)


def test_get_driver(target):
    class a():
        pass

    target.drivers.append(a())
    assert isinstance(target.get_driver(a), a)


def test_no_resource(target):
    with pytest.raises(NoResourceFoundError):
        target.get_resource(Target)


def test_no_driver(target):
    with pytest.raises(NoDriverFoundError):
        target.get_driver(Target)
