"""Unit tests for labgrid.remote.client"""

import argparse
from unittest.mock import MagicMock, patch

import pytest

from labgrid.driver import SerialDriver
from labgrid.protocol import ConsoleProtocol
from labgrid.remote.client import ClientSession, UserError, get_parser
from labgrid.resource import SerialPort


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


# --- _get_console() tests ---

class TestGetConsole:
    def test_uses_configured_driver(self, session):
        """A console driver from the environment config is used as is"""
        target = MagicMock()
        console = target.get_driver.return_value
        with patch.object(session, "_get_driver_or_new") as get_new:
            assert session._get_console(target, "uart") is console
        get_new.assert_not_called()

    def test_creates_serial_driver(self, session, target, mocker):
        """Without a console driver, one is created for the serial port"""
        mocker.patch("labgrid.driver.serialdriver.SerialDriver.on_activate")
        SerialPort(target, name=None, port="/dev/ttyUSB0")
        console = session._get_console(target)
        assert isinstance(console, SerialDriver)
        assert target.get_driver(ConsoleProtocol) is console
