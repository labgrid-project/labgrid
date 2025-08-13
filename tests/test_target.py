import abc
import re

import attr
import pytest

from labgrid import Target, target_factory
from labgrid.binding import BindingError
from labgrid.resource import Resource
from labgrid.driver import Driver
from labgrid.strategy import Strategy
from labgrid.exceptions import NoSupplierFoundError, NoDriverFoundError, NoResourceFoundError, NoStrategyFoundError


# test basic construction
def test_instanziation():
    t = Target("name")
    assert (isinstance(t, Target))


def test_get_resource(target):
    class A(Resource):
        pass

    a = A(target, "aresource")
    assert isinstance(target.get_resource(A), A)
    assert target.get_resource(A) is a
    assert target.get_resource(A, name="aresource") is a

    # make sure resources named "default" are prioritized
    b = A(target, "default")
    assert target.get_resource(A) is b
    assert target.get_resource(A, name="aresource") is a

def test_get_resource_multiple_no_default(target):
    class A(Resource):
        pass

    a = A(target, "aresource")
    b = A(target, "default")
    with pytest.raises(NoResourceFoundError) as excinfo:
        target.get_resource(A, name="nosuchresource")

def test_get_resource_multiple_with_default(target):
    class A(Resource):
        pass

    class B(Resource):
        pass

    a = A(target, "aresource")
    adef = A(target, "default")
    b = B(target, "bresource")
    bdef = B(target, "default")

    assert target.get_resource(A) is adef
    assert target.get_resource(B) is bdef
    assert target.get_resource(A, name="aresource") is a
    assert target.get_resource(B, name="bresource") is b

def test_get_driver(target):
    class A(Driver):
        pass

    a = A(target, "adriver")
    assert isinstance(target.get_driver(A), A)
    assert target.get_driver(A) is a
    assert target.get_driver(A, name="adriver") is a


def test_getitem(target):
    class AProtocol(abc.ABC):
        pass

    class A(Driver, AProtocol):
        pass

    class B(Driver):
        pass

    a = A(target, "adriver")
    target.activate(a)
    assert isinstance(target[A], A)
    assert target[A] is a
    assert target[AProtocol] is a
    assert target[A, "adriver"] is a
    assert target[AProtocol, "adriver"] is a
    with pytest.raises(NoDriverFoundError) as excinfo:
        target[A, "bdriver"]
    assert "matching resources with other names" in excinfo.value.msg
    with pytest.raises(NoDriverFoundError) as excinfo:
        target[B, "adriver"]
    assert re.match(f"no active .*? driver named '{a.name}' found in Target",
                    excinfo.value.msg)

    a2 = A(target, None)
    target.activate(a2)
    with pytest.raises(NoDriverFoundError) as excinfo:
        target[A]
    assert "multiple active drivers" in excinfo.value.msg


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
    ra = ResourceA(target, "resource")
    d = DriverWithA(target, "resource")
    assert d.res is ra


def test_suppliers_aset(target):
    ra = ResourceA(target, "resource")
    d = DriverWithASet(target, "driver")
    assert d.res is ra


def test_suppliers_ab_a(target):
    ra = ResourceA(target, "resource")
    d = DriverWithAB(target, "driver")
    assert d.res is ra


def test_suppliers_ab_b(target):
    rb = ResourceB(target, "resource")
    d = DriverWithAB(target, "driver")
    assert d.res is rb


def test_suppliers_ab_both(target):
    ra = ResourceA(target, "resource_a")
    rb = ResourceB(target, "resource_b")
    with pytest.raises(NoSupplierFoundError):
        d = DriverWithAB(target, "driver")


def test_suppliers_ab_missing(target):
    with pytest.raises(NoSupplierFoundError):
        d = DriverWithAB(target, "driver")


def test_suppliers_unexpected_binding(target):
    ra = ResourceA(target, "resource")
    target.set_binding_map({"res": "resource", "unexpected": "foo"})
    with pytest.raises(BindingError) as excinfo:
        DriverWithA(target, "driver")
    assert "got unexpected bindings" in excinfo.value.msg


class DriverWithNamedA(Driver):
    bindings = {
        "res": Driver.NamedBinding(ResourceA),
    }


def test_suppliers_named_a(target):
    ra = ResourceA(target, "resource")
    target.set_binding_map({"res": "resource"})
    d = DriverWithNamedA(target, "driver")
    assert d.res is ra


class DriverWithMultiA(Driver):
    bindings = {
        "res1": ResourceA,
        "res2": ResourceA,
    }


def test_suppliers_multi_a(target):
    ra1 = ResourceA(target, "resource1")
    with pytest.raises(BindingError) as excinfo:
        DriverWithMultiA(target, "driver")
    assert "duplicate bindings" in excinfo.value.msg


def test_suppliers_multi_a_explict(target):
    ra1 = ResourceA(target, "resource1")
    ra2 = ResourceA(target, "resource2")
    target.set_binding_map({
        "res1": "resource1",
        "res2": "resource2",
    })
    d = DriverWithMultiA(target, "driver")
    assert d.res1 is ra1
    assert d.res2 is ra2


class DriverWithNamedMultiA(Driver):
    bindings = {
        "res1": Driver.NamedBinding(ResourceA),
        "res2": Driver.NamedBinding(ResourceA),
    }


def test_suppliers_multi_named_a(target):
    ra1 = ResourceA(target, "resource1")
    ra2 = ResourceA(target, "resource2")
    target.set_binding_map({
        "res1": "resource1",
        "res2": "resource2",
    })
    d = DriverWithNamedMultiA(target, "driver")
    assert d.res1 is ra1
    assert d.res2 is ra2


# test optional bindings

class DriverWithOptionalA(Driver):
    bindings = {"res": {ResourceA, None}, }


class DriverWithOptionalAB(Driver):
    bindings = {"res": {ResourceA, ResourceB, None}, }


def test_suppliers_optional_a(target):
    ra = ResourceA(target, "resource")
    d = DriverWithOptionalA(target, "driver")
    assert d.res is ra


def test_suppliers_optional_a_missing(target):
    rb = ResourceB(target, "resource")
    d = DriverWithOptionalA(target, "driver")
    assert d.res is None


def test_suppliers_optional_ab_a(target):
    ra = ResourceA(target, "resource")
    d = DriverWithOptionalAB(target, "driver")
    assert d.res is ra


class DriverWithOptionalNamedA(Driver):
    bindings = {
        "res": Driver.NamedBinding({ResourceA, None}),
    }


def test_suppliers_optional_named_a(target):
    ra = ResourceA(target, "resource")
    target.set_binding_map({"res": "resource"})
    d = DriverWithOptionalNamedA(target, "driver")
    assert d.res is ra


def test_suppliers_optional_named_a_missing(target):
    rb = ResourceB(target, "resource")
    target.set_binding_map({"res": "resource"})
    d = DriverWithOptionalNamedA(target, "driver")
    assert d.res is None



class StrategyA(Strategy):
    bindings = {
        "drv": DriverWithA,
    }


def test_get_strategy(target):
    ra = ResourceA(target, "resource")
    d = DriverWithA(target, "driver")

    with pytest.raises(NoStrategyFoundError):
        target.get_strategy()

    s1 = StrategyA(target, "s1")
    assert target.get_strategy() is s1

    s2 = StrategyA(target, "s2")
    with pytest.raises(NoStrategyFoundError):
        target.get_strategy()


# test nested resource creation
@attr.s(eq=False)
class DiscoveryResource(Resource):
    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        ResourceA(self.target, "resource")

def test_nested(target):
    rd = DiscoveryResource(target, "discovery")
    d = DriverWithAB(target, "driver")
    assert isinstance(d.res, ResourceA)

# Test retrieving drivers, resources and protocols by name

def test_get_by_string(target):
    class AProtocol(abc.ABC):
        pass

    @target_factory.reg_driver
    class A(Driver, AProtocol):
        pass

    @target_factory.reg_driver
    class C(Resource):
        pass

    a = A(target, None)
    target.activate(a)
    assert target.get_driver('A') == a
    assert target.get_active_driver('A') == a

    c = C(target, None)
    assert target.get_resource('C') == c

    assert target['AProtocol'] == a

    with pytest.raises(KeyError):
        target.get_driver("nosuchdriver")

# Test priorities

def test_get_by_diff_priority(target):
    class AProtocol(abc.ABC):
        pass

    @attr.s
    class A(Driver, AProtocol):
        priorities = {AProtocol: -10}

    @attr.s
    class C(Driver, AProtocol):
        priorities = {AProtocol: 10}
        pass

    a = A(target, None)
    c = C(target, None)
    target.activate(a)
    target.activate(c)

    assert target.get_driver(AProtocol) == c

def test_get_by_same_priority(target):
    class AProtocol(abc.ABC):
        pass

    @attr.s
    class A(Driver, AProtocol):
        priorities = {AProtocol: 10}

    @attr.s
    class C(Driver, AProtocol):
        priorities = {AProtocol: 10}
        pass

    a = A(target, None)
    c = C(target, None)
    target.activate(a)
    target.activate(c)

    with pytest.raises(NoDriverFoundError) as e_info:
        target.get_driver(AProtocol)
    assert "multiple drivers matching" in str(e_info.value)

def test_get_by_default_priority(target):
    class AProtocol(abc.ABC):
        pass

    @attr.s
    class A(Driver, AProtocol):
        pass

    @attr.s
    class C(Driver, AProtocol):
        pass

    a = A(target, None)
    c = C(target, None)
    target.activate(a)
    target.activate(c)

    with pytest.raises(NoDriverFoundError) as e_info:
        target.get_driver(AProtocol)
    assert "multiple drivers matching" in str(e_info.value)

def test_target_deactivate_by_string(target):

    @target_factory.reg_driver
    @attr.s
    class ADea(Driver):
        pass

    a = ADea(target, None)
    target.activate(a)
    target.deactivate("ADea")

    assert a == target.get_driver(ADea, activate=False)

def test_target_activate_by_string(target):

    @target_factory.reg_driver
    @attr.s
    class AActiv(Driver):
        pass

    a = AActiv(target, None)
    target.activate("AActiv")

    assert a == target.get_active_driver(AActiv)

def test_allow_binding_by_different_protocols(target):
    class ADiffProtocol(abc.ABC):
        pass

    class BDiffProtocol(abc.ABC):
        pass

    class DiffDriver(Driver, ADiffProtocol, BDiffProtocol):
        pass

    class DiffStrategy(Strategy):
        bindings = {
            "a": ADiffProtocol,
            "b": BDiffProtocol
        }

    d = DiffDriver(target, None)
    s = DiffStrategy(target, None)

    assert s.a == d
    assert s.b == d

def test_allow_optional_binding_by_different_protocols(target):
    class AOpt1DiffProtocol(abc.ABC):
        pass

    class BOpt1DiffProtocol(abc.ABC):
        pass

    class Opt1DiffDriver(Driver, AOpt1DiffProtocol):
        pass

    class Opt1DiffStrategy(Strategy):
        bindings = {
            "a": AOpt1DiffProtocol,
            "b": {BOpt1DiffProtocol, None}
        }

    d = Opt1DiffDriver(target, None)
    s = Opt1DiffStrategy(target, None)

    assert s.a == d
    assert s.b == None

def test_allow_optional_available_binding_by_different_protocols(target):
    class AOpt2DiffProtocol(abc.ABC):
        pass

    class BOpt2DiffProtocol(abc.ABC):
        pass

    class Opt2DiffDriver(Driver, AOpt2DiffProtocol, BOpt2DiffProtocol):
        pass

    class Opt2DiffStrategy(Strategy):
        bindings = {
            "a": {AOpt2DiffProtocol, None},
            "b": {BOpt2DiffProtocol, None}
        }

    d = Opt2DiffDriver(target, None)
    s = Opt2DiffStrategy(target, None)

    assert s.a == d
    assert s.b == d

def test_allow_optional_no_available_binding_by_different_protocols(target):
    class AOpt3DiffProtocol(abc.ABC):
        pass

    class BOpt3DiffProtocol(abc.ABC):
        pass

    class Opt3DiffDriver(Driver):
        pass

    class Opt3DiffStrategy(Strategy):
        bindings = {
            "a": {AOpt3DiffProtocol, None},
            "b": {BOpt3DiffProtocol, None}
        }

    d = Opt3DiffDriver(target, None)
    s = Opt3DiffStrategy(target, None)

    assert s.a == None
    assert s.b == None

def test_allow_optional_no_double_same_protocol_by_different_protocols(target):
    class AOpt4DiffProtocol(abc.ABC):
        pass

    class Opt4DiffDriver(Driver, AOpt4DiffProtocol):
        pass

    class Opt4DiffStrategy(Strategy):
        bindings = {
            "a": {AOpt4DiffProtocol, None},
            "b": {AOpt4DiffProtocol, None},
            "c": {AOpt4DiffProtocol, None},
            "d": {AOpt4DiffProtocol, None},
        }

    d1 = Opt4DiffDriver(target, name="driver1")
    d2 = Opt4DiffDriver(target, name="driver2")
    target.set_binding_map({"c": "driver1", "d": "driver2"})
    s = Opt4DiffStrategy(target, None)

    assert s.a is None
    assert s.b is None
    assert s.c == d1
    assert s.d == d2

def test_get_bound_resources(target):
    class AResource(Resource):
        pass

    class ADriver(Driver):
        bindings = {
            "a": AResource,
        }

    class BDriver(Driver):
        bindings = {
            "a": ADriver,
        }

    aresource = AResource(target, "aresource")
    adriver = ADriver(target, "adriver")
    bdriver = BDriver(target, "bdriver")

    assert bdriver.get_bound_resources() == {aresource}
    assert adriver.get_bound_resources() == {aresource}

    assert target.get_driver(ADriver, resource=aresource) 

def test_get_bound_multiple_resources(target):
    class AResource(Resource):
        pass

    class BResource(Resource):
        pass

    class ADriver(Driver):
        bindings = {
            "a": AResource,
        }

    class BDriver(Driver):
        bindings = {
            "b": BResource,
        }

    class CDriver(Driver):
        bindings = {
            "a": ADriver,
            "b": BDriver,
        }

    aresource = AResource(target, "aresource")
    bresource = BResource(target, "bresource")
    adriver = ADriver(target, "adriver")
    bdriver = BDriver(target, "bdriver")
    cdriver = CDriver(target, "bdriver")

    assert adriver.get_bound_resources() == {aresource}
    assert bdriver.get_bound_resources() == {bresource}
    assert cdriver.get_bound_resources() == {aresource, bresource}

    assert target.get_driver(ADriver, resource=aresource) 
    assert target.get_driver(BDriver, resource=bresource) 
    assert target.get_driver(CDriver, resource=aresource) 

    assert target.get_active_driver(ADriver, resource=aresource) 
    assert target.get_active_driver(BDriver, resource=bresource) 
    assert target.get_active_driver(CDriver, resource=aresource) 
