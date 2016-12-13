import attr
import yaml
from .exceptions import NoConfigFoundError
from .target import Target


@attr.s
class Environment(object):
    config = attr.ib(defautl="config.yaml", validator=attr.validators.instance_of(str))

    """An environment encapsulates targets."""
    def __attr_post_init__(self):
        self.targets = {} #pylint: disable=attribute-defined-outside-init
        with open(self.config) as filename:
            try:
                self.config = yaml.load(filename) #pylint: disable=attribute-defined-outside-init
            except:
                raise NoConfigFoundError("{} could not be found".format(self.config))

        for target in self.config:
            self.targets[target] = Target(target)

    def get_target(self, role: str='main') -> Target:
        """Returns the specified target."""
        return self.targets[role]
