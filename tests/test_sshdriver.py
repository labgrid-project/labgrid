import pytest

from labgrid.driver import SSHDriver, ExecutionError
from labgrid.exceptions import NoResourceFoundError
from labgrid.resource import NetworkService

@pytest.fixture(scope='function')
def ssh_driver_mocked_and_activated(target, mocker):
        NetworkService(target, "service", "1.2.3.4", "root")
        call = mocker.patch('subprocess.call')
        call.return_value = 0
        popen = mocker.patch('subprocess.Popen', autospec=True)
        path = mocker.patch('os.path.exists')
        path.return_value = True
        instance_mock = mocker.MagicMock()
        popen.return_value = instance_mock
        instance_mock.wait = mocker.MagicMock(return_value=0)
        SSHDriver(target, "ssh")
        s = target.get_driver("SSHDriver")
        return s

class TestSSHDriver:
    def test_create_fail_missing_resource(self, target):
        with pytest.raises(NoResourceFoundError):
            SSHDriver(target, "ssh")

    def test_create(self, target, mocker):
        NetworkService(target, "service", "1.2.3.4", "root")
        call = mocker.patch('subprocess.call')
        call.return_value = 0
        popen = mocker.patch('subprocess.Popen', autospec=True)
        path = mocker.patch('os.path.exists')
        path.return_value = True
        instance_mock = mocker.MagicMock()
        popen.return_value = instance_mock
        instance_mock.wait = mocker.MagicMock(return_value=0)
        s = SSHDriver(target, "ssh")
        assert (isinstance(s, SSHDriver))

    def test_run_check(self, ssh_driver_mocked_and_activated, mocker):
        s = ssh_driver_mocked_and_activated
        s.run = mocker.MagicMock(return_value=[['success'],[],0])
        res = s.run_check("test")
        assert res == ['success']

    def test_run_check_raise(self, ssh_driver_mocked_and_activated, mocker):
        s = ssh_driver_mocked_and_activated
        s.run = mocker.MagicMock(return_value=[['error'],[],1])
        with pytest.raises(ExecutionError):
            res = s.run_check("test")
