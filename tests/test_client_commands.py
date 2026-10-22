import pytest

from labgrid.remote import client_commands
from labgrid.remote.client import get_parser


@pytest.fixture
def registry(monkeypatch):
    monkeypatch.setattr(client_commands, "_registry", {})
    return client_commands._registry


def make_command(name, **kwargs):
    @client_commands.client_command(name, **kwargs)
    class Command:
        """demo command"""

        @staticmethod
        def add_arguments(subparser):
            subparser.add_argument("value")

        @staticmethod
        def run(session, place, target):
            return (session, place, target)

    return Command


def test_registered_command_is_parsed(registry):
    make_command("demo", aliases=("d",))

    args = get_parser().parse_args(["demo", "x"])
    assert args.command == "demo"
    assert args.value == "x"
    assert get_parser().parse_args(["d", "y"]).value == "y"


def test_sync_command_resolves_place_and_target(registry):
    make_command("demo")

    class Session:
        def get_acquired_place(self):
            return "place"

        def _get_target(self, place):
            assert place == "place"
            return "target"

    args = get_parser().parse_args(["demo", "x"])
    session = Session()
    assert args.func(session) == (session, "place", "target")


def test_coroutine_command_is_marked_needs_target(registry):
    @client_commands.client_command("acmd")
    class AsyncCommand:
        @staticmethod
        def add_arguments(subparser):
            pass

        @staticmethod
        async def run(session, place, target):
            pass

    args = get_parser().parse_args(["acmd"])
    assert args.func.needs_target is True


def test_duplicate_registration_fails(registry):
    make_command("demo")
    with pytest.raises(ValueError, match="already registered"):
        make_command("demo")


@pytest.mark.parametrize("name, kwargs", [("power", {}), ("demo", {"aliases": ("pw",)})])
def test_collision_with_builtin_fails(registry, name, kwargs):
    make_command(name, **kwargs)
    with pytest.raises(ValueError, match="collides"):
        get_parser()


def test_broken_entry_point_only_warns(monkeypatch, capsys):
    class Broken:
        name = "broken"

        def load(self):
            raise ImportError("boom")

    monkeypatch.setattr(client_commands, "entry_points", lambda group: [Broken()])

    client_commands.load_entry_points()

    assert "broken failed to load: boom" in capsys.readouterr().err
