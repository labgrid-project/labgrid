from labgrid.resource import ManagedResource, Resource, ResourceManager


def test_create_resource(target):
    resource = Resource(target)

def test_create_managed_resource(target):
    resource_1 = ManagedResource(target)
    resource_2 = ManagedResource(target)
    assert resource_1.manager is resource_2.manager

def test_hash_is(target):
    resource1 = Resource(target)
    resource2 = Resource(target)
    assert resource1 is not resource2

def test_hash_set(target):
    resource1 = Resource(target)
    k = set()
    k.add(resource1)
    assert resource1 in k
