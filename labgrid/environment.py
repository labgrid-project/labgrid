import attr
import yaml
from .exceptions import NoConfigFoundError
from .target import Target


@attr.s
class Environment(object):
    def __attr_post_init__(self):
        config = 'board.yaml'
        with open(config) as f:
            try:
                self.config = yaml.load(f)
            except:
                raise NoConfigFoundError("{} could not be found".format(config))

        self.targets = {}
        for target in self.config:
            self.targets[target] = Target(target, self.config[target])

    def get_target(self, *, role: str='main') -> Target:
        return self.targets[role]
