from typing import Optional
import attr

from .target import Target
from .config import Config
from .util.imports import load_imports


@attr.s(eq=False)
class Environment:
    """An environment encapsulates targets."""
    config_file = attr.ib(
        default="config.yaml", validator=attr.validators.instance_of(str)
    )
    interact = attr.ib(default=input, repr=False)

    def __attrs_post_init__(self):
        self.targets = {}

        self.config = Config(self.config_file)

        load_imports(self.config.get_imports())

    def get_target(self, role: str = 'main') -> Optional[Target]:
        """Returns the specified target or None if not found.

        Each target is initialized as needed.
        """
        from . import target_factory

        if role not in self.targets:
            config = self.config.get_targets().get(role)
            if not config:
                return None
            target = target_factory.make_target(role, config, env=self)
            self.targets[role] = target

        return self.targets[role]

    def get_features(self):
        return self.config.get_features()

    def get_target_features(self):
        flags = set()
        for value in self.config.get_targets().values():
            flags = flags | set(value.get('features', {}))
        return flags

    def cleanup(self):
        for target in self.targets:
            self.targets[target].cleanup()
