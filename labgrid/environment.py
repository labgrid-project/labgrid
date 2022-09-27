import os
from typing import Optional
import attr

from .target import Target
from .config import Config


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

        for user_import in self.config.get_imports():
            import importlib.util
            from importlib.machinery import SourceFileLoader
            import sys

            if user_import.endswith('.py'):
                module_name = os.path.basename(user_import)[:-3]
                loader = SourceFileLoader(module_name, user_import)
                spec = importlib.util.spec_from_loader(loader.name, loader)
                module = importlib.util.module_from_spec(spec)
                loader.exec_module(module)
            else:
                module_name = user_import
                module = importlib.import_module(user_import)
            sys.modules[module_name] = module

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
