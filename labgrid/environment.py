import attr
import yaml
from .exceptions import NoConfigFoundError
from .target import Target

@attr.s
class Environment:
    """An environment encapsulates targets."""
    config_file = attr.ib(default="config.yaml", validator=attr.validators.instance_of(str))

    def __attrs_post_init__(self):
        from . import load_config
        from . import target_factory

        self.targets = {} #pylint: disable=attribute-defined-outside-init

        try:
            self.config = load_config(self.config_file) #pylint: disable=attribute-defined-outside-init
        except:
            raise NoConfigFoundError("{} is not a valid yaml file".format(self.config_file))

        for name, config in self.config.items():
            self.targets[name] = target_factory(name, config)

    def get_target(self, role: str='main') -> Target:
        """Returns the specified target."""
        return self.targets[role]
