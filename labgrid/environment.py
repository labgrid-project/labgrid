import attr
import yaml
from .exceptions import NoConfigFoundError
from .target import Target


@attr.s
class Environment(object):
    """An environment encapsulates targets."""
    def __attr_post_init__(self):
        config = 'board.yaml'
        with open(config) as filename:
            try:
                self.config = yaml.load(filename) #pylint: disable=attribute-defined-outside-init
            except:
                raise NoConfigFoundError("{} could not be found".format(config))

        self.targets = {} #pylint: disable=attribute-defined-outside-init
        for target in self.config:
            self.targets[target] = Target(target)

    def get_target(self, role: str='main') -> Target:
        """Returns the specified target."""
        return self.targets[role]
