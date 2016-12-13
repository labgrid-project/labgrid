import pytest

from labgrid.driver import ShellDriver, NoDriverException

class TestShellDriver:
    def test_instance(self, serial_driver):
        s = ShellDriver(serial_driver)
        assert(isinstance(s, ShellDriver))

    def test_no_driver(self, target):
        with pytest.raises(NoDriverException):
            ShellDriver(target)
