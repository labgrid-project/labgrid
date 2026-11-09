"""Unit tests for labgrid.remote.client"""

import argparse
from unittest.mock import MagicMock, patch

import pytest

from labgrid.remote.client import ClientSession, UserError, get_parser


# --- is_allowed() tests ---

@pytest.fixture
def session():
    """Create a minimal ClientSession-like object for testing"""
    s = object.__new__(ClientSession)
    s.args = argparse.Namespace()
    return s


@pytest.fixture
def mock_place():
    place = MagicMock()
    place.name = "testplace"
    place.acquired = "myhost/myuser"
    place.allowed = {"myhost/myuser"}
    return place


class TestIsAllowed:
    def test_place_not_acquired(self, session, mock_place):
        mock_place.acquired = None
        with patch.object(session, "gethostname", return_value="myhost"), \
             patch.object(session, "getuser", return_value="myuser"):
            result = session.is_allowed(mock_place)
        assert "not acquired" in result

    def test_place_acquired_by_us(self, session, mock_place):
        with patch.object(session, "gethostname", return_value="myhost"), \
             patch.object(session, "getuser", return_value="myuser"):
            result = session.is_allowed(mock_place)
        assert result is None

    def test_place_acquired_by_different_user(self, session, mock_place):
        mock_place.acquired = "myhost/otheruser"
        mock_place.allowed = {"myhost/otheruser"}
        with patch.object(session, "gethostname", return_value="myhost"), \
             patch.object(session, "getuser", return_value="myuser"):
            result = session.is_allowed(mock_place)
        assert "not acquired by your user" in result
        assert "otheruser" in result

    def test_place_acquired_on_different_host(self, session, mock_place):
        mock_place.acquired = "otherhost/myuser"
        mock_place.allowed = {"otherhost/myuser"}
        with patch.object(session, "gethostname", return_value="myhost"), \
             patch.object(session, "getuser", return_value="myuser"):
            result = session.is_allowed(mock_place)
        assert "not acquired on this computer" in result
        assert "otherhost" in result

    def test_place_acquired_elsewhere_but_allowed(self, session, mock_place):
        """User is in the allowed set even though place was acquired elsewhere"""
        mock_place.acquired = "otherhost/otheruser"
        mock_place.allowed = {"otherhost/otheruser", "myhost/myuser"}
        with patch.object(session, "gethostname", return_value="myhost"), \
             patch.object(session, "getuser", return_value="myuser"):
            result = session.is_allowed(mock_place)
        assert result is None


# --- _check_allowed() tests ---

class TestCheckAllowed:
    def test_raises_on_not_allowed(self, session, mock_place):
        mock_place.acquired = None
        with patch.object(session, "gethostname", return_value="myhost"), \
             patch.object(session, "getuser", return_value="myuser"):
            with pytest.raises(UserError, match="not acquired"):
                session._check_allowed(mock_place)

    def test_no_raise_when_allowed(self, session, mock_place):
        with patch.object(session, "gethostname", return_value="myhost"), \
             patch.object(session, "getuser", return_value="myuser"):
            session._check_allowed(mock_place)  # should not raise


# --- get_parser() tests ---

class TestGetParser:
    def test_console_internal_argument(self):
        parser = get_parser()
        args = parser.parse_args(["console", "--internal"])
        assert args.internal is True


# --- _console_commands() tests ---

class TestConsoleCommands:
    @pytest.fixture
    def commands(self, session, mock_place):
        session._power = MagicMock(return_value="power is on")
        return session._console_commands(mock_place, "target")

    def test_names(self, commands):
        names, _ = commands
        assert "help" in names
        assert "power cycle" in names
        assert "pw get" in names

    def test_power(self, session, mock_place, commands):
        _, handler = commands
        assert handler("pw get")() == "power is on"
        session._power.assert_called_with(mock_place, "target", "get", None, None)
        handler("power cycle -t 5 -n port1")()
        session._power.assert_called_with(mock_place, "target", "cycle", "port1", 5.0)

    def test_errors(self, session, commands):
        _, handler = commands
        assert "invalid choice: 'onn'" in handler("pw onn")
        assert "required: action" in handler("pw")
        assert "--delay" in handler("pw -h")
        assert handler("nope").startswith("unknown command 'nope'")
        session._power.assert_not_called()

    def test_help(self, commands):
        _, handler = commands
        msg = handler("help")
        assert "usage: power [-h]" in msg
        assert "(short: pw)" in msg
