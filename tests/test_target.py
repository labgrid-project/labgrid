import pytest

import attr

from labgrid import Target, target_factory
from labgrid.resource import Resource
from labgrid.driver import Driver
from labgrid.exceptions import NoSupplierFoundError, NoDriverFoundError, NoResourceFoundError


# test basic construction
def test_instanziation():
    t = Target("name")
    assert (isinstance(t, Target))


def test_get_resource(target):
    class a(Resource):
        pass

    a(target)
    assert isinstance(target.get_resource(a), a)


def test_get_driver(target):
    class a(Driver):
        pass

    a(target)
    assert isinstance(target.get_driver(a), a)


def test_no_resource(target):
    with pytest.raises(NoResourceFoundError):
        target.get_resource(Target)


def test_no_driver(target):
    with pytest.raises(NoDriverFoundError):
        target.get_driver(Target)


# test alternative suppliers
class ResourceA(Resource):
    pass


class ResourceB(Resource):
    pass


class DriverWithA(Driver):
    bindings = {"res": ResourceA}


class DriverWithASet(Driver):
    bindings = {"res": {ResourceA}, }


class DriverWithAB(Driver):
    bindings = {"res": {ResourceA, ResourceB}, }


def test_suppliers_a(target):
    ra = ResourceA(target)
    d = DriverWithA(target)
    assert d.res is ra


def test_suppliers_aset(target):
    ra = ResourceA(target)
    d = DriverWithASet(target)
    assert d.res is ra


def test_suppliers_ab_a(target):
    ra = ResourceA(target)
    d = DriverWithAB(target)
    assert d.res is ra


def test_suppliers_ab_b(target):
    rb = ResourceB(target)
    d = DriverWithAB(target)
    assert d.res is rb


def test_suppliers_ab_both(target):
    ra = ResourceA(target)
    rb = ResourceB(target)
    with pytest.raises(NoSupplierFoundError):
        d = DriverWithAB(target)


def test_suppliers_ab_missing(target):
    with pytest.raises(NoSupplierFoundError):
        d = DriverWithAB(target)

# test nested resource creation
@attr.s
class DiscoveryResource(Resource):
    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        ResourceA(self.target)

def test_nested(target):
    rd = DiscoveryResource(target)
    d = DriverWithAB(target)
    assert isinstance(d.res, ResourceA)
