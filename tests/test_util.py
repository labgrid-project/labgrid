import os.path
import subprocess
import socket
import atexit
import warnings

from shutil import which

import attr
import pytest
import logging

from labgrid.util import diff_dict, flat_dict, filter_dict
from labgrid.util.helper import get_free_port
from labgrid.util.ssh import ForwardError, SSHConnection, sshmanager
from labgrid.util.proxy import proxymanager
from labgrid.util.managedfile import ManagedFile
from labgrid.driver.exception import ExecutionError
from labgrid.resource.serialport import NetworkSerialPort
from labgrid.resource.common import Resource, NetworkResource
from labgrid.util import diff_dict, flat_dict, filter_dict, find_dict

@pytest.fixture
def connection_localhost():
    con = SSHConnection("localhost")
    con.connect()
    yield con
    con.disconnect()

@pytest.fixture
def connection_localhost_no_cleanup():
    con = SSHConnection("localhost")
    con.connect()
    return con

@pytest.fixture
def sshmanager_fix():
    yield sshmanager
    sshmanager.close_all()

def test_diff_dict():
    dict_a = {"a": 1,
              "b": 2}
    dict_b = {"a": 1,
              "b": 3}
    gen = diff_dict(dict_a, dict_b)
    for res in gen:
        assert res[0] == 'b'
        assert res[1] == 2
        assert res[2] == 3

def test_flat_dict():
    dict_a = {"a":
              {"b": 3},
              "b": 2}
    res = flat_dict(dict_a)
    assert res == {"a.b": 3, "b": 2}

def test_filter_dict():
    @attr.s
    class A:
        foo = attr.ib()

    d_orig = {'foo': 1, 'bar': 2, 'baz': 3}

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        d_filtered = filter_dict(d_orig, A)
    assert d_filtered is not d_orig
    assert d_filtered == {'foo': 1}

    with pytest.warns(UserWarning) as record:
        d_filtered = filter_dict(d_orig, A, warn=True)
    assert len(record) == 2
    assert str(record[0].message) == "unsupported attribute 'bar' with value '2' for class 'A'"
    assert str(record[1].message) == "unsupported attribute 'baz' with value '3' for class 'A'"
    assert d_filtered is not d_orig
    assert d_filtered == {'foo': 1}

def test_sshmanager_get():
    assert sshmanager != None

def test_sshconnection_get():
    from labgrid.util.ssh import SSHConnection
    SSHConnection("localhost")

@pytest.mark.skipif(not which("ssh"), reason="ssh not available")
def test_sshconnection_inactive_raise():
    from labgrid.util.ssh import SSHConnection
    con = SSHConnection("localhost")
    with pytest.raises(ExecutionError):
        con.run_check("echo Hallo")

@pytest.mark.localsshmanager
def test_sshconnection_connect(connection_localhost):
    assert connection_localhost.isconnected()
    assert os.path.exists(connection_localhost._socket)

@pytest.mark.localsshmanager
def test_sshconnection_run(connection_localhost):
    stdout, stderr, exitcode = connection_localhost.run("echo stderr >&2; echo stdout1; echo stdout2")
    assert exitcode == 0
    assert stderr == ["stderr"]
    assert stdout == ["stdout1", "stdout2"]

@pytest.mark.localsshmanager
def test_sshconnection_run_log(connection_localhost, caplog):
    caplog.set_level(logging.INFO)
    stdout, stderr, exitcode = connection_localhost.run("echo stderr >&2; echo stdout1; echo stdout2",
            stdout_loglevel=logging.INFO, stderr_loglevel=logging.WARNING)
    assert exitcode == 0
    assert stderr == ["stderr"]
    assert stdout == ["stdout1", "stdout2"]
    assert sorted([(rec[1], rec[2]) for rec in caplog.record_tuples]) == [
        (logging.INFO, 'stdout1'),
        (logging.INFO, 'stdout2'),
        (logging.WARNING, 'stderr'),
   ]

@pytest.mark.localsshmanager
def test_sshconnection_run_merged_stderr(connection_localhost):
    stdout, stderr, exitcode = connection_localhost.run(
            "echo stderr >&2; echo stdout", stderr_merge=True)
    assert exitcode == 0
    assert sorted(stdout) == ["stderr", "stdout"]
    assert stderr == []

@pytest.mark.localsshmanager
def test_sshconnection_run_fail(connection_localhost):
    stdout, stderr, exitcode = connection_localhost.run("false")
    assert exitcode != 0


@pytest.mark.localsshmanager
def test_sshconnection_port_forward_add_remove(connection_localhost):
    port = get_free_port()
    test_string = "Hello World"

    local_port = connection_localhost.add_port_forward('localhost', port)
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(("127.0.0.1", port))
    server_socket.listen(1)
    send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    send_socket.connect(("127.0.0.1", local_port))
    client_socket, address = server_socket.accept()
    send_socket.send(test_string.encode('utf-8'))

    assert client_socket.recv(16).decode("utf-8") == test_string
    connection_localhost.remove_port_forward('localhost', port)

@pytest.mark.localsshmanager
def test_sshconnection_port_forward_remove_raise(connection_localhost):
    port = get_free_port()

    with pytest.raises(ForwardError):
        connection_localhost.remove_port_forward('localhost', port)

@pytest.mark.localsshmanager
def test_sshconnection_port_forward_add_duplicate(connection_localhost):
    port = get_free_port()

    first_port = connection_localhost.add_port_forward('localhost', port)
    second_port = connection_localhost.add_port_forward('localhost', port)
    assert first_port == second_port


@pytest.mark.localsshmanager
def test_sshconnection_port_remote_forward_add_remove(connection_localhost):
    rport = get_free_port()
    lport = get_free_port()
    test_string = "Hello World"

    connection_localhost.add_remote_port_forward(rport, lport)
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(("127.0.0.1", lport))
    server_socket.listen(1)
    send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    send_socket.connect(("127.0.0.1", rport))
    client_socket, address = server_socket.accept()
    send_socket.send(test_string.encode('utf-8'))

    assert client_socket.recv(16).decode("utf-8") == test_string
    connection_localhost.remove_remote_port_forward(rport, lport)
    assert connection_localhost._r_forwards == set()


@pytest.mark.localsshmanager
def test_sshconnection_put_file(connection_localhost, tmpdir):
    p = tmpdir.join("config.yaml")
    p.write(
        """Teststring"""
    )
    connection_localhost.put_file(p, '/tmp/test')

    assert os.path.isfile('/tmp/test')
    assert open('/tmp/test', 'r').readlines() == [ "Teststring" ]

@pytest.mark.localsshmanager
def test_sshconnection_get_file(connection_localhost, tmpdir):

    p = tmpdir.join("test")
    connection_localhost.get_file('/tmp/test', p)

@pytest.mark.localsshmanager
def test_sshconnection_cleanup(connection_localhost_no_cleanup):

    connection_localhost_no_cleanup.cleanup()

    # do not call cleanup() again on termination
    atexit.unregister(connection_localhost_no_cleanup.cleanup)

@pytest.mark.localsshmanager
def test_sshmanager_open(sshmanager_fix):
    con = sshmanager_fix.open("localhost")

    assert isinstance(con, SSHConnection)

@pytest.mark.localsshmanager
def test_sshmanager_add_forward(sshmanager_fix):
    port = sshmanager_fix.request_forward("localhost", 'localhost', 3000)

    assert port < 65536

@pytest.mark.localsshmanager
def test_sshmanager_remove_forward(sshmanager_fix):
    port = sshmanager_fix.request_forward("localhost", 'localhost', 3000)
    sshmanager_fix.remove_forward('localhost', 'localhost', 3000)

    assert 3000 not in sshmanager_fix.get('localhost')._l_forwards

@pytest.mark.localsshmanager
def test_sshmanager_close(sshmanager_fix):
    con = sshmanager_fix.open("localhost")

    assert isinstance(con, SSHConnection)
    sshmanager_fix.close("localhost")

@pytest.mark.localsshmanager
def test_sshmanager_remove_raise(sshmanager_fix):
    con = sshmanager_fix.open("localhost")
    con.connect()
    with pytest.raises(ExecutionError):
        sshmanager_fix.remove_connection(con)

@pytest.mark.skipif(not which("ssh"), reason="ssh not available")
def test_sshmanager_add_duplicate(sshmanager_fix):
    host = 'localhost'
    con = SSHConnection(host)
    sshmanager_fix.add_connection(con)
    con_there = sshmanager_fix._connections[host]
    sshmanager_fix.add_connection(con)
    con_now = sshmanager_fix._connections[host]

    assert con_now == con_there

@pytest.mark.skipif(not which("ssh"), reason="ssh not available")
def test_sshmanager_add_new(sshmanager_fix):
    host = 'other_host'
    con = SSHConnection(host)
    sshmanager_fix.add_connection(con)
    con_now = sshmanager_fix._connections[host]

    assert con_now == con

@pytest.mark.skipif(not which("ssh"), reason="ssh not available")
def test_sshmanager_invalid_host_raise():
    con = SSHConnection("nosuchhost.notavailable")
    with pytest.raises(ExecutionError):
        con.connect()

def test_proxymanager_no_proxy(target):
    host = 'localhost'
    port = 5000
    nr = NetworkSerialPort(target, host=host, port=port, name=None)
    nr.proxy = ''
    nr.proxy_required = False

    assert (host, port) == proxymanager.get_host_and_port(nr)

@pytest.mark.localsshmanager
def test_proxymanager_remote_forced_proxy(target):
    sshmanager.close_all()
    host = 'localhost'
    port = 5000
    nr = NetworkSerialPort(target, host=host, port=port, name=None)
    extras = { 'proxy': 'localhost', 'proxy_required': True }
    nr.extra = extras
    nhost, nport = proxymanager.get_host_and_port(nr)

    assert (host, port) != (nhost, nport)
    sshmanager.close_all()

@pytest.mark.localsshmanager
def test_proxymanager_local_forced_proxy(target):
    host = 'localhost'
    port = 5000
    nr = NetworkSerialPort(target, host=host, port=port, name=None)
    extras = { 'proxy': 'localhost', 'proxy_required': True }
    nr.extra = extras
    nhost, nport = proxymanager.get_host_and_port(nr)

    assert (host, port) != (nhost, nport)

@pytest.mark.localsshmanager
def test_remote_managedfile(target, tmpdir):
    import hashlib
    import getpass

    res = NetworkResource(target, "test", "localhost")
    t = tmpdir.join("test")
    t.write(
"""
Test
"""
    )
    hash = hashlib.sha256(t.read().encode("utf-8")).hexdigest()
    mf = ManagedFile(t, res, detect_nfs=False)
    mf.sync_to_resource()

    assert os.path.isfile(f"/var/cache/labgrid/{getpass.getuser()}/{hash}/test")
    assert hash == mf.get_hash()
    assert f"/var/cache/labgrid/{getpass.getuser()}/{hash}/test" == mf.get_remote_path()

@pytest.mark.localsshmanager
def test_remote_managedfile_on_nfs(target, tmpdir):
    res = NetworkResource(target, "test", "localhost")
    t = tmpdir.join("test")
    t.write(
"""
Test
"""
    )
    mf = ManagedFile(t, res, detect_nfs=True)
    mf.sync_to_resource()

    assert str(t) == mf.get_remote_path()

def test_local_managedfile(target, tmpdir):
    import hashlib

    res = Resource(target, "test")
    t = tmpdir.join("test")
    t.write(
"""
Test
"""
    )
    hash = hashlib.sha256(t.read().encode("utf-8")).hexdigest()
    mf = ManagedFile(t, res, detect_nfs=False)
    mf.sync_to_resource()

    assert hash == mf.get_hash()
    assert str(t) == mf.get_remote_path()


def test_find_dict():
    dict_a = {"a": {"a.a": {"a.a.a": "a.a.a_val"}}, "b": "b_val"}
    assert find_dict(dict_a, "b") == "b_val"
    assert find_dict(dict_a, "a") == {"a.a": {"a.a.a": "a.a.a_val"}}
    assert find_dict(dict_a, "a.a") == {"a.a.a": "a.a.a_val"}
    assert find_dict(dict_a, "a.a.a") == "a.a.a_val"
    assert find_dict(dict_a, "x") == None
