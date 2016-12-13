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

    def __call__(self, name, config):
        from .target import Target

        role = config.get('role', name)
        target = Target(name)
        for resource, args in config.get('resources', {}).items():
            assert isinstance(args, dict)
            r = self.resources[resource](**args)
            target.add_resource(r)
        for driver, args in config.get('drivers', {}).items():
            assert isinstance(args, dict)
            d = self.drivers[driver](target, **args)
            target.add_driver(d)
        return target

target_factory = TargetFactory()
