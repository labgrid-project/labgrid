import os
from unittest.mock import AsyncMock, patch

import pytest

from labgrid.driver.power.tapo import _get_credentials, power_get, power_set


@pytest.fixture
def mock_device_strip():
    device = AsyncMock()
    device.children = [AsyncMock(is_on=True), AsyncMock(is_on=False), AsyncMock(is_on=True)]
    return device


@pytest.fixture
def mock_device_single_plug():
    device = AsyncMock()
    device.children = []
    return device


@pytest.fixture
def mock_env():
    os.environ["KASA_USERNAME"] = "test_user"
    os.environ["KASA_PASSWORD"] = "test_pass"
    yield
    del os.environ["KASA_USERNAME"]
    del os.environ["KASA_PASSWORD"]


class TestTapoPowerDriver:
    def test_get_credentials_should_raise_value_error_when_credentials_missing(self):
        # Save existing environment variables
        saved_username = os.environ.pop("KASA_USERNAME", None)
        saved_password = os.environ.pop("KASA_PASSWORD", None)

        try:
            with pytest.raises(EnvironmentError, match="KASA_USERNAME or KASA_PASSWORD environment variable not set"):
                _get_credentials()
        finally:
            # Restore environment variables if they existed
            if saved_username is not None:
                os.environ["KASA_USERNAME"] = saved_username
            if saved_password is not None:
                os.environ["KASA_PASSWORD"] = saved_password

    def test_credentials_valid(self, mock_env):
        creds = _get_credentials()
        assert creds.username == "test_user"
        assert creds.password == "test_pass"

    def test_power_get_single_plug_turn_on(self, mock_device_single_plug, mock_env):
        mock_device_single_plug.is_on = True

        with patch("kasa.Device.connect", return_value=mock_device_single_plug):
            result = power_get("192.168.1.100", None, "0")
            assert result is True

    def test_power_get_single_plug_turn_off(self, mock_device_single_plug, mock_env):
        mock_device_single_plug.is_on = False

        with patch("kasa.Device.connect", return_value=mock_device_single_plug):
            result = power_get("192.168.1.100", None, "0")
            assert result is False

    def test_power_get_single_plug_should_not_care_for_index(self, mock_device_single_plug, mock_env):
        invalid_index_ignored = "7"
        mock_device_single_plug.is_on = True

        with patch("kasa.Device.connect", return_value=mock_device_single_plug):
            result = power_get("192.168.1.100", None, invalid_index_ignored)
            assert result is True

    def test_power_set_single_plug_turn_on(self, mock_device_single_plug, mock_env):
        mock_device_single_plug.is_on = False
        with patch("kasa.Device.connect", return_value=mock_device_single_plug):
            power_set("192.168.1.100", None, "0", True)
            mock_device_single_plug.turn_on.assert_called_once()

    def test_power_set_single_plug_turn_off(self, mock_device_single_plug, mock_env):
        mock_device_single_plug.is_on = True
        with patch("kasa.Device.connect", return_value=mock_device_single_plug):
            power_set("192.168.1.100", None, "0", False)
            mock_device_single_plug.turn_off.assert_called_once()

    def test_power_get_strip_valid_socket(self, mock_device_strip, mock_env):
        with patch("kasa.Device.connect", return_value=mock_device_strip):
            # Test first outlet (on)
            result = power_get("192.168.1.100", None, "0")
            assert result is True

            # Test second outlet (off)
            result = power_get("192.168.1.100", None, "1")
            assert result is False

            # Test third outlet (on)
            result = power_get("192.168.1.100", None, "2")
            assert result is True

    def test_power_set_strip_valid_socket(self, mock_device_strip, mock_env):
        with patch("kasa.Device.connect", return_value=mock_device_strip):
            power_set("192.168.1.100", None, "0", False)
            mock_device_strip.children[0].turn_off.assert_called_once()

            power_set("192.168.1.100", None, "1", True)
            mock_device_strip.children[1].turn_on.assert_called_once()

    def test_power_get_should_raise_assertion_error_when_invalid_index_strip(self, mock_device_strip, mock_env):
        invalid_socket = "5"
        with patch("kasa.Device.connect", return_value=mock_device_strip), \
                pytest.raises(AssertionError, match="Trying to access non-existent plug socket"):
            power_get("192.168.1.100", None, invalid_socket)

    def test_power_set_should_raise_assertion_error_when_invalid_index_strip(self, mock_device_strip, mock_env):
        invalid_socket = "5"
        with patch("kasa.Device.connect", return_value=mock_device_strip), \
                pytest.raises(AssertionError, match="Trying to access non-existent plug socket"):
            power_set("192.168.1.100", None, invalid_socket, True)

    def test_port_not_none_strip(self, mock_device_strip):
        with patch("kasa.Device.connect", return_value=mock_device_strip), \
                pytest.raises(AssertionError):
            power_get("192.168.1.100", "8080", "0")

    def test_port_not_none_single_socket(self, mock_device_single_plug):
        mock_device_single_plug.is_on = True
        with patch("kasa.Device.connect", return_value=mock_device_single_plug), \
                pytest.raises(AssertionError):
            power_get("192.168.1.100", "8080", "0")
