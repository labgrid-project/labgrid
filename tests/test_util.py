import os.path
import subprocess
import socket

import attr
import pytest

from labgrid.util import diff_dict, flat_dict, filter_dict
from labgrid.util.ssh import ForwardError, SSHConnection, sshmanager
from labgrid.util.proxy import proxymanager
from labgrid.util.managedfile import ManagedFile
from labgrid.driver.exception import ExecutionError
from labgrid.resource.serialport import NetworkSerialPort
from labgrid.resource.common import Resource, NetworkResource

@pytest.fixture
def connection_localhost():
    con = SSHConnection("localhost")
    con.connect()
    yield con
    con.disconnect()

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

    with pytest.warns(None) as record:
        d_filtered = filter_dict(d_orig, A)
    assert not record
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

def test_sshconnection_inactive_raise():
    from labgrid.util.ssh import SSHConnection
    con = SSHConnection("localhost")
    with pytest.raises(ExecutionError):
        con.run_command("echo Hallo")

def test_sshconnection_connect(connection_localhost):
    assert connection_localhost.isconnected()
    assert os.path.exists(connection_localhost._socket)

def test_sshconnection_run(connection_localhost):
    assert connection_localhost.run_command("echo Hello") == 0

def test_sshconnection_port_forward_add_remove(connection_localhost):
    port = 1337
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

def test_sshconnection_port_forward_remove_raise(connection_localhost):
    port = 1337

    with pytest.raises(ForwardError):
        connection_localhost.remove_port_forward('localhost', port)

def test_sshconnection_port_forward_add_duplicate(connection_localhost):
    port = 1337

    first_port = connection_localhost.add_port_forward('localhost', port)
    second_port = connection_localhost.add_port_forward('localhost', port)
    assert first_port == second_port


def test_sshconnection_put_file(connection_localhost, tmpdir):
    port = 1337

    p = tmpdir.join("config.yaml")
    p.write(
        """Teststring"""
    )
    connection_localhost.put_file(p, '/tmp/test')

    assert os.path.isfile('/tmp/test')
    assert open('/tmp/test', 'r').readlines() == [ "Teststring" ]

def test_sshconnection_get_file(connection_localhost, tmpdir):

    p = tmpdir.join("test")
    connection_localhost.get_file('/tmp/test', p)

def test_sshmanager_open(sshmanager_fix):
    con = sshmanager_fix.open("localhost")

    assert isinstance(con, SSHConnection)

def test_sshmanager_add_forward(sshmanager_fix):
    port = sshmanager_fix.request_forward("localhost", 'localhost', 3000)

    assert port < 65536

def test_sshmanager_remove_forward(sshmanager_fix):
    port = sshmanager_fix.request_forward("localhost", 'localhost', 3000)
    sshmanager_fix.remove_forward('localhost', 'localhost', 3000)

    assert 3000 not in sshmanager_fix.get('localhost')._forwards

def test_sshmanager_close(sshmanager_fix):
    con = sshmanager_fix.open("localhost")

    assert isinstance(con, SSHConnection)
    sshmanager_fix.close("localhost")

def test_sshmanager_remove_raise(sshmanager_fix):
    con = sshmanager_fix.open("localhost")
    con.connect()
    with pytest.raises(ExecutionError):
        sshmanager_fix.remove_connection(con)

def test_sshmanager_add_duplicate(sshmanager_fix):
    host = 'localhost'
    con = SSHConnection(host)
    sshmanager_fix.add_connection(con)
    con_there = sshmanager_fix._connections[host]
    sshmanager_fix.add_connection(con)
    con_now = sshmanager_fix._connections[host]

    assert con_now == con_there

def test_sshmanager_add_new(sshmanager_fix):
    host = 'other_host'
    con = SSHConnection(host)
    sshmanager_fix.add_connection(con)
    con_now = sshmanager_fix._connections[host]

    assert con_now == con


def test_sshmanager_remove_raise():
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

def test_proxymanager_local_forced_proxy(target):
    host = 'localhost'
    port = 5000
    nr = NetworkSerialPort(target, host=host, port=port, name=None)
    extras = { 'proxy': 'localhost', 'proxy_required': True }
    nr.extra = extras
    nhost, nport = proxymanager.get_host_and_port(nr)

    assert (host, port) != (nhost, nport)

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
    mf = ManagedFile(t, res)
    mf.sync_to_resource()

    assert os.path.isfile("/tmp/labgrid-{}/{}/test".format(getpass.getuser(), hash))
    assert hash == mf.get_hash()
    assert "/tmp/labgrid-{}/{}/test".format(getpass.getuser(), hash) == mf.get_remote_path()

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
    mf = ManagedFile(t, res)
    mf.sync_to_resource()

    assert hash == mf.get_hash()
    assert str(t) == mf.get_remote_path()
