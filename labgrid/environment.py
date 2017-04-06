import attr
import yaml

from .exceptions import NoConfigFoundError
from .target import Target
from .config import Config


@attr.s
class Environment:
    """An environment encapsulates targets."""
    config_file = attr.ib(
        default="config.yaml", validator=attr.validators.instance_of(str)
    )
    interact = attr.ib(default=input, repr=False)

    def __attrs_post_init__(self):
        self.targets = {}  #pylint: disable=attribute-defined-outside-init

        try:
            self.config = Config(self.config_file)
        except:
            raise NoConfigFoundError(
                "{} is not a valid yaml file".format(self.config_file)
            )

    def get_target(self, role: str='main') -> Target:
        """Returns the specified target.

        Each target is initialized as needed.
        """
        from . import target_factory

        if not role in self.targets:
            config = self.config.get_targets()[role]
            target = target_factory.make_target(role, config, env=self)
            self.targets[role] = target

        return self.targets[role]

    def cleanup(self):
        for target in self.targets:
            self.targets[target].cleanup()
