from .exceptions import InvalidConfigError

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

    def _convert_to_named_list(self, data):
        """Convert a tree of resources or drivers to a named list.

        When using named resources or drivers, the config file uses a list of
        dicts instead of simply nested dicts. This allows creating multiple
        instances of the same class with different names.

        resources: # or drivers
          FooPort: {}
          BarPort:
            name: "bar"

        or

        resources: # or drivers
        - FooPort: {}
        - BarPort:
            name: "bar"

        should be transformed to

        resources: # or drivers
        - cls: "FooPort"
        - cls: "BarPort"
          name: "bar"
        """

        # resolve syntactic sugar (list of dicts each containing a dict of key -> args)
        if isinstance(data, list):
            for idx, item in enumerate(data):
                if not isinstance(item, dict):
                    raise InvalidConfigError(
                        "invalid list item type {} (should be dict)".format(type(item)))
                if len(item) < 1:
                    raise InvalidConfigError("invalid empty dict as list item")
                if len(item) > 1:
                    if 'cls' in item:
                        continue
                    else:
                        raise InvalidConfigError("missing 'cls' key in {}".format(item))
                # only one pair left
                (key, value), = item.items()
                if key == 'cls':
                    continue
                else:
                    item.clear()
                    item['cls'] = key
                    item.update(value)
            result = data
        elif isinstance(data, dict):
            result = []
            for cls, args in data.items():
                args.setdefault('cls', cls)
                result.append(args)
        else:
            raise InvalidConfigError("invalid type {} (should be dict or list)".format(type(data)))
        for item in result:
            item.setdefault('name', None)
            assert 'cls' in item
        return result

    def make_resource(self, target, resource, name, args):
        assert isinstance(args, dict)
        if not resource in self.resources:
            raise InvalidConfigError("unknown resource class {}".format(resource))
        try:
            r = self.resources[resource](target, name, **args)
        except TypeError as e:
            raise InvalidConfigError(
                "failed to create {} for target '{}' using {} ".format(
                    resource, target, args)) from e
        return r

    def make_driver(self, target, driver, name, args):
        assert isinstance(args, dict)
        if not driver in self.drivers:
            raise InvalidConfigError("unknown driver class {}".format(driver))
        try:
            d = self.drivers[driver](target, name, **args)
        except TypeError as e:
            raise InvalidConfigError(
                "failed to create {} for target '{}' using {} ".format(
                    driver, target, args)) from e
        return d

    def make_target(self, name, config, *, env=None):
        from .target import Target

        role = config.get('role', name)
        target = Target(name, env=env)
        for item in self._convert_to_named_list(config.get('resources', {})):
            resource = item.pop('cls')
            name = item.pop('name', None)
            args = item # remaining args
            r = self.make_resource(target, resource, name, args)
        for item in self._convert_to_named_list(config.get('drivers', {})):
            driver = item.pop('cls')
            name = item.pop('name', None)
            bindings = item.pop('bindings', {})
            args = item # remaining args
            target.set_binding_map(bindings)
            d = self.make_driver(target, driver, name, args)
        return target


#: Global TargetFactory instance
#:
#: This instance is used to register Resource and Driver classes so that
#: Targets can be created automatically from YAML files.
target_factory = TargetFactory()
