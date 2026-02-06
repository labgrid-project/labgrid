from .target import Target
from .environment import Environment
from .exceptions import NoConfigFoundError

from .factory import target_factory
from .step import step, steps
from .stepreporter import StepReporter
from .consoleloggingreporter import ConsoleLoggingReporter
from .plugins.manager import load_plugins

try:
    from ._version import __version__
except ImportError:
    __version__ = "unknown"

# Load labgrid plugins after all internal objects are created.
load_plugins([target_factory])
