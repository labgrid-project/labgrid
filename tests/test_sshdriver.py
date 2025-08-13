import pytest
import socket

from labgrid import Environment
from labgrid.driver import SSHDriver, ExecutionError
from labgrid.exceptions import NoResourceFoundError
from labgrid.resource import NetworkService
from labgrid.util.helper import get_free_port

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
    instance_mock.communicate = mocker.MagicMock(return_value=(b"", b""))
    SSHDriver(target, "ssh")
    s = target.get_driver("SSHDriver")
    return s

def test_create_fail_missing_resource(target):
    with pytest.raises(NoResourceFoundError):
        SSHDriver(target, "ssh")

def test_create(target, mocker):
    NetworkService(target, "service", "1.2.3.4", "root")
    call = mocker.patch('subprocess.call')
    call.return_value = 0
    popen = mocker.patch('subprocess.Popen', autospec=True)
    path = mocker.patch('os.path.exists')
    path.return_value = True
    instance_mock = mocker.MagicMock()
    popen.return_value = instance_mock
    instance_mock.wait = mocker.MagicMock(return_value=0)
    instance_mock.communicate = mocker.MagicMock(return_value=(b"", b""))
    s = SSHDriver(target, "ssh")
    assert isinstance(s, SSHDriver)

def test_run_check(target, ssh_driver_mocked_and_activated, mocker):
    s = ssh_driver_mocked_and_activated
    s._run = mocker.MagicMock(return_value=(['success'], [], 0))
    res = s.run_check("test")
    assert res == ['success']
    res = s.run("test")
    assert res == (['success'], [], 0)
    target.deactivate(s)

def test_run_check_raise(target, ssh_driver_mocked_and_activated, mocker):
    s = ssh_driver_mocked_and_activated
    s._run = mocker.MagicMock(return_value=(['error'], [], 1))
    with pytest.raises(ExecutionError):
        res = s.run_check("test")
    res = s.run("test")
    assert res == (['error'], [], 1)
    target.deactivate(s)

def test_default_tools(target):
    NetworkService(target, "service", "1.2.3.4", "root")
    s = SSHDriver(target, "ssh")
    assert [s._ssh, s._scp, s._sshfs, s._rsync] == ["ssh", "scp", "sshfs", "rsync"]

def test_custom_tools(target, tmpdir):
    p = tmpdir.join("config.yaml")
    p.write(
        """
        tools:
          ssh: "/path/to/ssh"
          scp: "/path/to/scp"
          sshfs: "/path/to/sshfs"
          rsync: "/path/to/rsync"
        """
    )
    target.env = Environment(str(p))
    NetworkService(target, "service", "1.2.3.4", "root")
    s = SSHDriver(target, "ssh")
    assert [s._ssh, s._scp, s._sshfs, s._rsync] == [f"/path/to/{t}" for t in ("ssh", "scp", "sshfs", "rsync")]

@pytest.fixture(scope='function')
def ssh_localhost(target, pytestconfig):
    name = pytestconfig.getoption("--ssh-username")
    NetworkService(target, "service", "localhost", name)
    SSHDriver(target, "ssh")
    s = target.get_driver("SSHDriver")
    return s

@pytest.mark.sshusername
def test_local_put(ssh_localhost, tmpdir):
    p = tmpdir.join("config.yaml")
    p.write(
        """PUT Teststring"""
    )

    ssh_localhost.put(str(p), "/tmp/test_put_yaml")
    assert open('/tmp/test_put_yaml', 'r').readlines() == [ "PUT Teststring" ]

@pytest.mark.sshusername
def test_local_no_final_line_remove(ssh_localhost, tmpdir):
    p = tmpdir.join("test_no_line_remove")
    p.write("teststring")

    ssh_localhost.put(str(p), "/tmp/test_line_remove")
    stdout, stderr, _ = ssh_localhost.run("cat /tmp/test_line_remove")
    assert stdout == [ "teststring" ]

@pytest.mark.sshusername
def test_local_final_line_remove_empty(ssh_localhost, tmpdir):
    p = tmpdir.join("test_no_line_remove")
    p.write("teststring\n")

    ssh_localhost.put(str(p), "/tmp/test_line_remove")
    stdout, stderr, _ = ssh_localhost.run("cat /tmp/test_line_remove")
    assert stdout == [ "teststring" ]

@pytest.mark.sshusername
def test_local_put_dir(ssh_localhost, tmpdir):
    d = tmpdir.mkdir("test_put_dir");
    p = d.join("config.yaml")
    p.write(
        """PUT Teststring"""
    )

    ssh_localhost.put(str(d), "/tmp/test_put_dir")
    assert open('/tmp/test_put_dir/config.yaml', 'r').readlines() == [ "PUT Teststring" ]

@pytest.mark.sshusername
def test_local_get(ssh_localhost, tmpdir):
    p = tmpdir.join("config.yaml")
    p.write(
        """GET Teststring"""
    )

    ssh_localhost.get(str(p), "/tmp/test_get_yaml")
    assert open('/tmp/test_get_yaml', 'r').readlines() == [ "GET Teststring" ]

@pytest.mark.sshusername
def test_local_get_dir(ssh_localhost, tmpdir):
    d = tmpdir.mkdir("test_get_dir");
    p = d.join("config.yaml")
    p.write(
        """GET Teststring"""
    )

    ssh_localhost.get(str(d), "/tmp/test_get_dir")
    assert open('/tmp/test_get_dir/config.yaml', 'r').readlines() == [ "GET Teststring" ]

@pytest.mark.sshusername
def test_local_run(ssh_localhost, tmpdir):

    res = ssh_localhost.run("echo Hello")
    assert res == (["Hello"], [], 0)

@pytest.mark.sshusername
def test_local_run_check(ssh_localhost, tmpdir):

    res = ssh_localhost.run_check("echo Hello")
    assert res == (["Hello"])

@pytest.mark.sshusername
def test_local_port_forward(ssh_localhost, tmpdir):
    remoteport = get_free_port()
    test_string = "Hello World"

    with ssh_localhost.forward_local_port(remoteport) as localport:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as send_socket:
                server_socket.bind(("127.0.0.1", remoteport))
                server_socket.listen(1)

                send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                send_socket.connect(("127.0.0.1", localport))

                client_socket, address = server_socket.accept()
                send_socket.send(test_string.encode('utf-8'))

                assert client_socket.recv(16).decode("utf-8") == test_string

@pytest.mark.sshusername
def test_local_remote_forward(ssh_localhost, tmpdir):
    remoteport = get_free_port()
    localport = get_free_port()
    test_string = "Hello World"

    with ssh_localhost.forward_remote_port(remoteport, localport):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as send_socket:
                server_socket.bind(("127.0.0.1", localport))
                server_socket.listen(1)

                send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                send_socket.connect(("127.0.0.1", remoteport))

                client_socket, address = server_socket.accept()
                send_socket.send(test_string.encode('utf-8'))

                assert client_socket.recv(16).decode("utf-8") == test_string


@pytest.mark.sshusername
def test_unix_socket_forward(ssh_localhost, tmpdir):
    p = tmpdir.join("console.sock")
    test_string = "Hello World"

    with ssh_localhost.forward_unix_socket(str(p)) as localport:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server_socket:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as send_socket:
                server_socket.bind(str(p))
                server_socket.listen(1)

                send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                send_socket.connect(("127.0.0.1", localport))

                client_socket, address = server_socket.accept()
                send_socket.send(test_string.encode("utf-8"))

                assert client_socket.recv(16).decode("utf-8") == test_string
