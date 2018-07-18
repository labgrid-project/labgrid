import os.path
import subprocess

import attr
import pytest

from labgrid.util import diff_dict, flat_dict, filter_dict
from labgrid.util.ssh import ForwardError
from labgrid.util.ssh import SSHConnection
from labgrid.driver.exception import ExecutionError

@pytest.fixture
def connection_localhost():
    con = SSHConnection("localhost")
    con.connect()
    yield con
    con.disconnect()

@pytest.fixture
def sshmanager():
    from labgrid.util.ssh import SSHMANAGER
    return SSHMANAGER

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
    from labgrid.util.ssh import SSHMANAGER
    assert SSHMANAGER != None

def test_sshconnection_get():
    from labgrid.util.ssh import SSHConnection
    SSHConnection("localhost")

def test_sshconnection_inactive_raise():
    from labgrid.util.ssh import SSHConnection
    con = SSHConnection("localhost")
    with pytest.raises(ExecutionError):
        con.run_command("echo Hallo")

def test_sshconnection_connect(connection_localhost):
    assert connection_localhost.isactive()
    assert os.path.exists(connection_localhost._socket)

def test_sshconnection_run(connection_localhost):
    assert connection_localhost.run_command("echo Hello") == 0

def test_sshconnection_port_forward_add_remove(connection_localhost):
    port = 1337
    test_string = "Hello World"

    local_port = connection_localhost.add_port_forward(port)
    nc_listen = subprocess.Popen(["nc", "-l", "-p", "1337"], stdout=subprocess.PIPE, stdin=None)
    nc_send = subprocess.Popen(["nc", "localhost", "{}".format(local_port)], stdin=subprocess.PIPE,stdout=None)
    try:
        nc_send.communicate("Hello World".encode("utf-8"), timeout=1)
    except subprocess.TimeoutExpired:
        pass
    nc_listen.terminate()
    assert nc_listen.communicate()[0].decode("utf-8") == test_string
    connection_localhost.remove_port_forward(port)

def test_sshconnection_port_forward_remove_raise(connection_localhost):
    port = 1337

    with pytest.raises(ForwardError):
        connection_localhost.remove_port_forward(port)

def test_sshconnection_port_forward_add_duplicate(connection_localhost):
    port = 1337

    first_port =  connection_localhost.add_port_forward(port)
    second_port = connection_localhost.add_port_forward(port)
    assert first_port == second_port


def test_sshconnection_put_file(connection_localhost, tmpdir):
    port = 1337

    p = tmpdir.join("config.yaml")
    p.write(
        """
Teststring
    """
    )
    connection_localhost.put_file(p, '/tmp/test')

def test_sshconnection_get_file(connection_localhost, tmpdir):

    p = tmpdir.join("test")
    connection_localhost.get_file('/tmp/test', p)

def test_sshmanager_open(sshmanager):
    con = sshmanager.open("localhost")
    assert isinstance(con, SSHConnection)

def test_sshmanager_add_forward(sshmanager):
    port = sshmanager.request_forward("localhost", 3000)
    assert port < 65536

def test_sshmanager_remove_forward(sshmanager):
    sshmanager.remove_forward('localhost', 3000)
    assert 3000 not in sshmanager.get('localhost')._forwards

def test_sshmanager_close(sshmanager):
    con = sshmanager.open("localhost")
    assert isinstance(con, SSHConnection)
    sshmanager.close("localhost")

def test_sshmanager_remove_raise(sshmanager):
    con = sshmanager.open("localhost")
    con.connect()
    with pytest.raises(ExecutionError):
        sshmanager.remove_connection(con)

def test_sshmanager_add_duplicate(sshmanager):
    host = 'localhost'
    con_there = sshmanager._connections[host]
    con = SSHConnection(host)
    sshmanager.add_connection(con)
    con_now = sshmanager._connections[host]
    assert con_now == con_there

def test_sshmanager_add_new(sshmanager):
    host = 'other_host'
    con = SSHConnection(host)
    sshmanager.add_connection(con)
    con_now = sshmanager._connections[host]
    assert con_now == con


def test_sshmanager_remove_raise(sshmanager):
    con = SSHConnection("nosuchhost.notavailable")
    with pytest.raises(ExecutionError):
        con.connect()
