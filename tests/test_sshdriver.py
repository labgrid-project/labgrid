import pytest
from labgrid.driver import SSHDriver, NoResourceError
from labgrid.resource import NetworkService


class TestSSHDriver:
    def test_create_fail_missing_resource(self, target):
        with pytest.raises(NoResourceError):
            SSHDriver(target)

    def test_create(self, target):
        target.add_resource(NetworkService("1.2.3.4"))
        s = SSHDriver(target)
        assert(isinstance(s, SSHDriver))
