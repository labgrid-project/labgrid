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

    def test_get_resource(self, target):
        class a():
            pass
        target.drivers.append(a())
        assert isinstance(target.get_driver(a),a)

    def test_no_resource(self, target):
        assert target.get_resource(Target) == None

    def test_no_driver(self, target):
        assert target.get_driver(Target) == None


