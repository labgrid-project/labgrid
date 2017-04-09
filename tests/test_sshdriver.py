import pytest

from labgrid.driver import SSHDriver
from labgrid.exceptions import NoResourceFoundError
from labgrid.resource import NetworkService


class TestSSHDriver:
    def test_create_fail_missing_resource(self, target):
        with pytest.raises(NoResourceFoundError):
            SSHDriver(target)

    def test_create(self, target, mocker):
        NetworkService(target, "1.2.3.4", "root")
        call = mocker.patch('subprocess.call')
        call.return_value = 0
        popen = mocker.patch('subprocess.Popen', autospec=True)
        path = mocker.patch('os.path.exists')
        path.return_value = True
        instance_mock = mocker.MagicMock()
        popen.return_value = instance_mock
        instance_mock.wait = mocker.MagicMock(return_value=0)
        s = SSHDriver(target)
        assert (isinstance(s, SSHDriver))
