import pytest

from labgrid.driver import ShellDriver
from labgrid.exceptions import NoDriverFoundError


class TestShellDriver:
    def test_instance(self, target, serial_driver):
        s = ShellDriver(target, "", "", "")
        assert (isinstance(s, ShellDriver))

    def test_no_driver(self, target):
        with pytest.raises(NoDriverFoundError):
            ShellDriver(target, "", "", "")
