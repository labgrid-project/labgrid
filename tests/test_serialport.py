from unittest.mock import MagicMock, patch
from mock_import import mock_import
import pytest
import serial
from labgrid.resource import SerialPort
from labgrid import Target

class TestSerialPort:
    def test_instanziation(self, monkeypatch):
        t = Target("Test")
        serial_mock = MagicMock
        monkeypatch.setattr(serial, 'Serial', serial_mock)
        s = SerialPort(t,'port')
        assert(isinstance(s, SerialPort))
        assert(t.resources[0] == s)
