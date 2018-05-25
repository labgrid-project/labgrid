from labgrid.resource import ManagedResource, Resource


def test_create_resource(target):
    resource = Resource(target, "resource")

def test_create_managed_resource(target):
    resource_1 = ManagedResource(target, "managedr1")
    resource_2 = ManagedResource(target, "managedr2")
    assert resource_1.manager is resource_2.manager

def test_hash_is(target):
    resource1 = Resource(target, "resource1")
    resource2 = Resource(target, "resource2")
    assert resource1 is not resource2

def test_hash_set(target):
    resource1 = Resource(target, "resource")
    k = set()
    k.add(resource1)
    assert resource1 in k
