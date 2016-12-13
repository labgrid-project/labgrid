import pytest

from labgrid.driver import ShellDriver, NoDriveError

class TestShellDriver:
    def test_instance(self, serial_driver):
        s = ShellDriver(serial_driver)
        assert(isinstance(s, ShellDriver))

    def test_no_driver(self, target):
        with pytest.raises(NoDriveError):
            ShellDriver(target)
