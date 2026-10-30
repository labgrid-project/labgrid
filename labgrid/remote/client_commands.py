"""Registry for ``labgrid-client`` subcommands contributed by plugins.

A plugin module (listed under ``imports:`` in the environment, or exposed
through the ``labgrid.client_commands`` entry-point group) decorates a class
with :func:`client_command`. The client installs the registered commands into
its argument parser before parsing the command line.
"""

import inspect
import sys
from importlib.metadata import entry_points

ENTRY_POINT_GROUP = "labgrid.client_commands"

_registry = {}


class ClientCommandError(ValueError):
    """A plugin command cannot be registered or installed."""


def client_command(name, *, aliases=()):
    """Register a class as ``labgrid-client`` subcommand ``name``.

    The class provides ``add_arguments(subparser)`` to declare its arguments
    and ``run(session, place, target)``, which may be a coroutine function.
    """

    def decorator(cls):
        if name in _registry:
            raise ClientCommandError(f"client command {name!r} is already registered by {_registry[name].__module__}")
        cls.lg_command_name = name
        cls.lg_command_aliases = tuple(aliases)
        _registry[name] = cls
        return cls

    return decorator


def load_entry_points():
    """Import installed plugins; a broken plugin must not break the built-in commands."""
    for entry_point in entry_points(group=ENTRY_POINT_GROUP):
        try:
            entry_point.load()
        except Exception as e:
            print(f"warning: client command plugin {entry_point.name} failed to load: {e}", file=sys.stderr)


def install(subparsers):
    """Add all registered commands to the ``labgrid-client`` subparsers."""
    for name, cls in _registry.items():
        for key in (name, *cls.lg_command_aliases):
            if key in subparsers.choices:
                raise ClientCommandError(
                    f"client command {key!r} from {cls.__module__} collides with an existing command"
                )
        subparser = subparsers.add_parser(name, aliases=cls.lg_command_aliases, help=inspect.getdoc(cls))
        cls.add_arguments(subparser)
        subparser.set_defaults(func=_make_func(cls))


def _make_func(cls):
    if inspect.iscoroutinefunction(cls.run):
        # the client dispatcher passes (session, place, target) to such functions
        cls.run.needs_target = True
        return cls.run

    def func(session):
        place = session.get_acquired_place()
        target = session._get_target(place)
        return cls.run(session, place, target)

    return func
