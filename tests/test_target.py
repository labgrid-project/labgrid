import pytest
from labgrid.driver import NoResourceException
from labgrid import Target

class TestTarget:
    def test_instanziation(self):
        t = Target("name")
        assert(isinstance(t, Target))

    def test_get_resource(self, target):
        class a():
            pass
        target.resources.append(a())
        assert isinstance(target.get_resource(a),a)

    def test_add_resource(self, target):
        class a():
            pass
        target.add_resource(a())
        assert isinstance(target.get_resource(a),a)

    def test_rm_resource_fail(self, target):
        class a():
            pass
        with pytest.raises(NoResourceException):
            target.rm_resource(a())
            assert isinstance(target.get_resource(a),a)

    def test_rm_resource(self, target):
        class a():
            pass
        k = a()
        target.resources.append(k)
        target.rm_resource(k)
        assert(target.resources == [])

    def test_get_driver(self, target):
        class a():
            pass
        target.drivers.append(a())
        assert isinstance(target.get_driver(a),a)

    def test_no_resource(self, target):
        assert target.get_resource(Target) == None

    def test_no_driver(self, target):
        assert target.get_driver(Target) == None


