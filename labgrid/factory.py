class TargetFactory:
    def __init__(self):
        self.resources = {}
        self.drivers = {}

    def reg_resource(self, cls):
        """Register a resource with the factory.

        Returns the class to allow using it as a decorator."""
        self.resources[cls.__name__] = cls
        return cls

    def reg_driver(self, cls):
        """Register a driver with the factory.

        Returns the class to allow using it as a decorator."""
        self.drivers[cls.__name__] = cls
        return cls

    def make_resource(self, target, resource, args):
        assert isinstance(args, dict)
        r = self.resources[resource](target, **args)
        return r

    def make_target(self, name, config, *, env=None):
        from .target import Target

        role = config.get('role', name)
        target = Target(name, env=env)
        for resource, args in config.get('resources', {}).items():
            r = self.make_resource(target, resource, args)
        for driver, args in config.get('drivers', {}).items():
            assert isinstance(args, dict)
            d = self.drivers[driver](target, **args)
        return target


#: Global TargetFactory instance
#:
#: This instance is used to register Resource and Driver classes so that
#: Targets can be created automatically from YAML files.
target_factory = TargetFactory()
