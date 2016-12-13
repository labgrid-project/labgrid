import pytest
from labgrid.driver import SSHDriver, NoResourceException
from labgrid.resource import NetworkService


class TestSSHDriver:
    def test_create_fail_missing_resource(self, target):
        with pytest.raises(NoResourceException):
            SSHDriver(target)

    def test_create(self, target):
        target.add_resource(NetworkService())
        s = SSHDriver(target)
        assert(isinstance(s, SSHDriver))
