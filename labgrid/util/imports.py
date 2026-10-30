import importlib
import importlib.util
import os
import sys
from importlib.machinery import SourceFileLoader

_loaded = set()


def load_imports(user_imports):
    """Import the modules or .py files listed in the ``imports`` key of an environment config.

    Each entry is imported only once per process: re-executing a file would
    make factory registrations fail with a RegistrationError.
    """
    for user_import in user_imports:
        # the same file may be reached through different relative paths
        key = os.path.realpath(user_import) if user_import.endswith(".py") else user_import
        if key in _loaded:
            continue

        if user_import.endswith(".py"):
            module_name = os.path.basename(user_import)[:-3]
            loader = SourceFileLoader(module_name, user_import)
            spec = importlib.util.spec_from_loader(loader.name, loader)
            module = importlib.util.module_from_spec(spec)
            loader.exec_module(module)
        else:
            module_name = user_import
            module = importlib.import_module(user_import)
        sys.modules[module_name] = module
        _loaded.add(key)
