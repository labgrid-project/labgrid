import inspect

from .exceptions import InvalidConfigError, RegistrationError
from .util.dict import filter_dict


class TargetFactory:
    def __init__(self):
        self.resources = {}
        self.drivers = {}
        self.all_classes = {}

    def reg_resource(self, cls):
        """Register a resource with the factory.

        Returns the class to allow using it as a decorator."""
        cls_name = cls.__name__
        if cls_name in self.all_classes:
            raise RegistrationError(f"resource with name {cls_name} was already registered")
        self.resources[cls.__name__] = cls
        self._insert_into_all(cls)
        return cls

    def reg_driver(self, cls):
        """Register a driver with the factory.

        Returns the class to allow using it as a decorator."""
        cls_name = cls.__name__
        if cls_name in self.all_classes:
            raise RegistrationError(f"driver with name {cls_name} was already registered")
        self.drivers[cls_name] = cls
        self._insert_into_all(cls)
        return cls

    @staticmethod
    def _convert_to_named_list(data):
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
        result = []
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    raise InvalidConfigError(
                        f"invalid list item type {type(item)} (should be dict)")
                if not item:
                    raise InvalidConfigError("invalid empty dict as list item")
                if len(item) > 1:
                    if 'cls' in item:
                        item = item.copy()
                    else:
                        raise InvalidConfigError(f"missing 'cls' key in {item}")
                else:
                    # only one pair left
                    (key, value), = item.items()
                    if key == 'cls':
                        item = item.copy()
                    else:
                        item = {'cls':  key}
                        if value is None:
                            raise InvalidConfigError("invalid list item, add empty dict for no arguments")  # pylint: disable=line-too-long
                        item.update(value)
                result.append(item)
        elif isinstance(data, dict):
            for cls, args in data.items():
                args = args.copy()
                args.setdefault('cls', cls)
                result.append(args)
        else:
            raise InvalidConfigError(f"invalid type {type(data)} (should be dict or list)")
        for item in result:
            item.setdefault('name', None)
            assert 'cls' in item
        return result

    @staticmethod
    def normalize_config(config):
        resources = {}
        drivers = {}
        for item in TargetFactory._convert_to_named_list(config.get('resources', {})):
            resource = item.pop('cls')
            name = item.pop('name', None)
            args = item # remaining args
            resources.setdefault(resource, {})[name] = (args, )
        for item in TargetFactory._convert_to_named_list(config.get('drivers', {})):
            driver = item.pop('cls')
            name = item.pop('name', None)
            bindings = item.pop('bindings', {})
            args = item # remaining args
            drivers.setdefault(driver, {})[name] = (args, bindings)
        return resources, drivers

    def make_resource(self, target, resource, name, args):
        assert isinstance(args, dict)
        if not resource in self.resources:
            raise InvalidConfigError(f"unknown resource class {resource}")
        try:
            cls = self.resources[resource]
            args = filter_dict(args, cls, warn=True)
            r = cls(target, name, **args)
        except TypeError as e:
            raise InvalidConfigError(
                f"failed to create {resource} for target '{target}' using {args} "
            ) from e
        return r

    def make_driver(self, target, driver, name, args):
        assert isinstance(args, dict)
        if not driver in self.drivers:
            raise InvalidConfigError(f"unknown driver class {driver}")
        try:
            cls = self.drivers[driver]
            args = filter_dict(args, cls, warn=True)
            d = cls(target, name, **args)
        except TypeError as e:
            raise InvalidConfigError(
                f"failed to create {driver} for target '{target}' using {args} ") from e
        return d

    def make_target(self, name, config, *, env=None):
        from .target import Target

        target = Target(name, env=env)
        for item in TargetFactory._convert_to_named_list(config.get('resources', {})):
            resource = item.pop('cls')
            name = item.pop('name', None)
            args = item # remaining args
            self.make_resource(target, resource, name, args)
        for item in TargetFactory._convert_to_named_list(config.get('drivers', {})):
            driver = item.pop('cls')
            name = item.pop('name', None)
            bindings = item.pop('bindings', {})
            args = item # remaining args
            target.set_binding_map(bindings)
            self.make_driver(target, driver, name, args)
        return target

    def class_from_string(self, string: str):
        try:
            return self.all_classes[string]
        except KeyError:
            raise KeyError(f"No driver/resource/protocol of type '{string}' in factory, perhaps not registered?")

    def _insert_into_all(self, cls):
        classes = inspect.getmro(cls)
        for cl in classes:
            if not self.all_classes.get(cl.__name__):
                self.all_classes[cl.__name__] = cl


#: Global TargetFactory instance
#:
#: This instance is used to register Resource and Driver classes so that
#: Targets can be created automatically from YAML files.
target_factory = TargetFactory()
