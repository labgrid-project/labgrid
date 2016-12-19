import pytest
import time

from labgrid.driver import ExternalConsoleDriver


class TestExternalConsoleDriver:
    def test_create(self, target):
        d = ExternalConsoleDriver(target, 'cat')
        assert (isinstance(d, ExternalConsoleDriver))

    def test_communicate(self, target):
        data = b"test\ndata"
        d = ExternalConsoleDriver(target, 'cat')
        d.write(data)
        time.sleep(0.1)
        assert d.read() == data
        d.close()
