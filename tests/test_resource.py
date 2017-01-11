from labgrid.resource import ManagedResource, Resource, ResourceManager


def test_create_resource(target):
    resource = Resource(target)

def test_create_managed_resource(target):
    resource_1 = ManagedResource(target)
    resource_2 = ManagedResource(target)
    assert resource_1.manager is resource_2.manager
