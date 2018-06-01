import pytest
from py.path import local
import tempfile
import os

from labgrid.external import RemoteTmpdir

from labgrid.driver import SSHDriver, ExecutionError
from labgrid.exceptions import NoResourceFoundError
from labgrid.resource import NetworkService


@pytest.fixture(scope='function')
def ssh_driver_mocked_and_activated(target, mocker):
    def dummy():
        def Popen(cmd, stdout=None, stderr=None):
            class xx:
                returncode = 0
                def communicate(*x):
                    if "mktemp" in cmd:
                        return b'/tmp/tmp.aaaa\n', b''
                    else:
                        return b'', b''
            return xx
        return Popen
    NetworkService(target, "service", "1.2.3.4", "root")
    call = mocker.patch('subprocess.call')
    call.return_value = 0
    popen = mocker.patch('subprocess.Popen', new_callable=dummy)
    path = mocker.patch('os.path.exists')
    path.return_value = True
    instance_mock = mocker.MagicMock()
    popen.return_value = instance_mock
    instance_mock.wait = mocker.MagicMock(return_value=0)
    SSHDriver(target, "ssh")
    s = target.get_driver("SSHDriver")
    return s


class TestTmpdir:

    def test_create(self, ssh_driver_mocked_and_activated, mocker):
        s = ssh_driver_mocked_and_activated
        s.run = mocker.MagicMock(return_value=[['/tmp/mock.dir'], [], 0])
        remote = RemoteTmpdir(s)
        assert remote.path.startswith('/tmp')

    def xtest_create_filetransfer(self, ssh_driver_mocked_and_activated, mocker):
        s = ssh_driver_mocked_and_activated
        s.run = mocker.MagicMock(return_value=[['/tmp/mock.dir'], [], 0])
        remote = RemoteTmpdir(s, filetransfer=s)
        assert remote.path.startswith('/tmp')

    def xtest_put(self, ssh_driver_mocked_and_activated, mocker):
        s = ssh_driver_mocked_and_activated
        s.run = mocker.MagicMock(return_value=[['/tmp/mock.dir'], [], 0])
        remote = RemoteTmpdir(s,os.path.dirname(__file__))

        s.run = mocker.MagicMock(return_value=[['success'], [], 0])

        remote.put(__file__)
        remote.put(os.path.basename(__file__))
        remote.put(__file__,__file__)
        remote.get("remotefile", "localfile")
        remote.get("remotefile")
