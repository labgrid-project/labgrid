import attr
import yaml
from .exceptions import NoConfigFoundError
from .target import Target


@attr.s
class Environment:
    """An environment encapsulates targets."""
    config_file = attr.ib(default="config.yaml", validator=attr.validators.instance_of(str))

    def __attrs_post_init__(self):
        self.targets = {} #pylint: disable=attribute-defined-outside-init

        try:
            filename = open(self.config_file)
        except:
            raise NoConfigFoundError("{} could not be found".format(self.config_file))

        with filename:
            try:
                self.config = yaml.load(filename) #pylint: disable=attribute-defined-outside-init
            except:
                raise NoConfigFoundError("{} is not a valid yaml file".format(self.config_file))

        for target in self.config:
            self.targets[target] = Target(target)

    def get_target(self, role: str='main') -> Target:
        """Returns the specified target."""
        return self.targets[role]
