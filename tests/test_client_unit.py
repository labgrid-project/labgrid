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


# --- set_initial_state() / set_end_state() tests ---

class TestStateTransitions:
    def test_set_initial_state_no_state(self, session):
        """No-op when args.state is not set"""
        session.args.state = None
        target = MagicMock()
        session.set_initial_state(target)
        target.get_driver.assert_not_called()

    def test_set_initial_state_with_state(self, session):
        session.args.state = "uboot"
        session.args.initial_state = None
        target = MagicMock()
        strategy = MagicMock()
        target.get_driver.return_value = strategy

        session.set_initial_state(target)

        target.get_driver.assert_called_once_with("Strategy")
        strategy.transition.assert_called_once_with("uboot")
        strategy.force.assert_not_called()

    def test_set_initial_state_with_force(self, session):
        session.args.state = "uboot"
        session.args.initial_state = "off"
        target = MagicMock()
        strategy = MagicMock()
        target.get_driver.return_value = strategy

        session.set_initial_state(target)

        strategy.force.assert_called_once_with("off")
        strategy.transition.assert_called_once_with("uboot")

    def test_set_end_state_no_state(self, session):
        session.args.end_state = None
        target = MagicMock()
        session.set_end_state(target)
        target.get_driver.assert_not_called()

    def test_set_end_state_with_state(self, session):
        session.args.end_state = "off"
        target = MagicMock()
        strategy = MagicMock()
        target.get_driver.return_value = strategy

        session.set_end_state(target)

        target.get_driver.assert_called_once_with("Strategy")
        strategy.transition.assert_called_once_with("off")

    def test_set_end_state_none_target_no_state(self, session):
        """set_end_state with no end_state is a no-op even with None target"""
        session.args.end_state = None
        session.set_end_state(None)  # should not raise


# --- get_parser() tests ---

class TestGetParser:
    def test_acquire_argument(self):
        parser = get_parser()
        args = parser.parse_args(["-a", "acquire"])
        assert args.acquire is True

    def test_end_state_argument(self):
        parser = get_parser()
        args = parser.parse_args(["-e", "off", "places"])
        assert args.end_state == "off"

    def test_release_force_argument(self):
        parser = get_parser()
        args = parser.parse_args(["release", "--force"])
        assert args.force is True

    def test_console_internal_argument(self):
        parser = get_parser()
        args = parser.parse_args(["console", "--internal"])
        assert args.internal is True

    def test_acquire_flag(self):
        parser = get_parser()
        args = parser.parse_args(["-a", "places"])
        assert args.acquire is True

    def test_defaults(self):
        parser = get_parser()
        args = parser.parse_args(["places"])
        assert args.acquire is False
        assert args.end_state is None

    def test_release_has_no_auto_attribute(self):
        """The release subparser defines --force, not --auto.

        The _release_place() code checks args.auto, but that attribute
        is never defined by any argument. This test documents the
        mismatch — it should probably be args.force instead.
        """
        parser = get_parser()
        args = parser.parse_args(["release"])
        assert not hasattr(args, "auto") or args.auto is None
        assert hasattr(args, "force")
