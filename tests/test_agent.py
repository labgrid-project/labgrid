import os
import socket
import subprocess

import pytest
from py.path import local

import labgrid.util.agentwrapper
from labgrid.util.agentwrapper import AgentError, AgentException, AgentWrapper, b2s, s2b

@pytest.fixture(scope='function')
def subprocess_mock(mocker):
    import subprocess

    original = subprocess.Popen

    agent = local(labgrid.util.agentwrapper.__file__).dirpath('agent.py')

    def run(args, **kwargs):
        assert args[0] in ['rsync', 'ssh']
        if args[0] == 'rsync':
            src = local(args[-2])
            assert src == agent
            dst = args[-1]
            assert ':' in dst
            dst = dst.split(':', 1)[1]
            assert '/' not in dst
            assert dst.startswith('.labgrid_agent')
            return original(['true'], **kwargs)
        elif args[0] == 'ssh':
            assert '--' in args
            args = args[args.index('--')+1:]
            assert len(args) == 2
            assert args[0] == 'python3'
            assert args[1].startswith('.labgrid_agent')
            # we need to use the original here to get the coverage right
            return original(['python3', str(agent)], **kwargs)

    mocker.patch('subprocess.Popen', run)

def test_create(subprocess_mock):
    aw = AgentWrapper('localhost')
    aw.close()

def test_call(subprocess_mock):
    aw = AgentWrapper('localhost')
    assert aw.call('test') == []
    assert aw.call('test', 0) == [0]
    assert aw.call('test', 0, 1) == [1, 0]
    assert aw.call('test', 'foo') == ['foo']
    assert aw.call('test', '{') == ['{']

def test_proxy(subprocess_mock):
    aw = AgentWrapper('localhost')
    assert aw.test() == []
    assert aw.test( 0, 1) == [1, 0]

def test_bytes(subprocess_mock):
    aw = AgentWrapper('localhost')
    assert s2b(aw.test(b2s(b'\x00foo'))[0]) == b'\x00foo'

def test_exception(subprocess_mock):
    aw = AgentWrapper('localhost')

    with pytest.raises(AgentException) as excinfo:
        aw.error('foo')
    assert excinfo.value.args == ("ValueError('foo')",)

    with pytest.raises(AgentException) as excinfo:
        aw.error('bar')
    assert excinfo.value.args == ("ValueError('bar')",)

def test_error(subprocess_mock):
    aw = AgentWrapper('localhost')
    aw.agent.stdin.write(b'\x00')
    with pytest.raises(AgentError):
        aw.test()

def test_module(subprocess_mock):
    aw = AgentWrapper('localhost')
    dummy = aw.load('dummy')
    assert dummy.neg(1) == -1

def test_local():
    aw = AgentWrapper(None)

    assert aw.test() == []
    assert aw.test( 0, 1) == [1, 0]

    assert s2b(aw.test(b2s(b'\x00foo'))[0]) == b'\x00foo'

    with pytest.raises(AgentException) as excinfo:
        aw.error('foo')
    assert excinfo.value.args == ("ValueError('foo')",)

    with pytest.raises(AgentException) as excinfo:
        aw.error('bar')
    assert excinfo.value.args == ("ValueError('bar')",)

    dummy = aw.load('dummy')
    assert dummy.neg(1) == -1


def test_local_fdpass():
    aw = AgentWrapper(None)

    result = aw.test_fd()
    assert isinstance(result, tuple)
    assert result[0] == "dummy"
    assert isinstance(result[1], int)

    with os.fdopen(result[1]) as f:
        fdpath = os.readlink(f"/proc/self/fd/{f.fileno()}")
        assert fdpath.startswith("/memfd:test_fd")


def test_all_modules():
    aw = AgentWrapper(None)
    aw.load('deditec_relais8')
    methods = aw.list()
    assert 'deditec_relais8.set' in methods
    assert 'deditec_relais8.get' in methods
    aw.load('sysfsgpio')
    methods = aw.list()
    assert 'sysfsgpio.set' in methods
    assert 'sysfsgpio.get' in methods
    aw.load('usb_hid_relay')
    methods = aw.list()
    assert 'usb_hid_relay.set' in methods
    assert 'usb_hid_relay.get' in methods

def test_import_modules():
    import labgrid.util.agents
    import labgrid.util.agents.dummy
    from labgrid.util.agents import deditec_relais8, sysfsgpio


def test_network_namespace():
    with AgentWrapper(None) as aw:
        netns = aw.load('netns')

        ns_pid = netns.unshare()
        assert ns_pid > 0

        tun_name, tun_fd = netns.create_tun(address="be:df:8f:7a:12:db")

        links = netns.get_links()
        link_names = [link["ifname"] for link in links]
        assert "tap0" in link_names

        _, fd = netns.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        with socket.socket(fileno=fd) as s:
            assert s.getsockopt(socket.SOL_SOCKET, socket.SO_PROTOCOL) == socket.IPPROTO_TCP

        _, fd = netns.create_socket(socket.AF_INET, socket.SOCK_DGRAM)
        with socket.socket(fileno=fd) as s:
            assert s.getsockopt(socket.SOL_SOCKET, socket.SO_PROTOCOL) == socket.IPPROTO_UDP


@pytest.mark.parametrize("family,host",
    [
        pytest.param(socket.AF_INET, "127.0.0.1", id="IPv4"),
        pytest.param(socket.AF_INET6, "::1", id="IPv6"),
    ]
)
def test_network_namespace_sockets(family, host):
    with AgentWrapper(None) as aw:
        netns = aw.load('netns')

        ns_pid = netns.unshare()
        assert ns_pid > 0

        tun_name, tun_fd = netns.create_tun(address="be:df:8f:7a:12:db")

        links = netns.get_links()
        link_names = [link["ifname"] for link in links]
        assert "tap0" in link_names

        # Bring up lo in the namespace
        subprocess.run(netns.get_prefix() + ["ip", "link", "set", "up", "dev", "lo"], check=True)

        # Test TCP connections
        _, fd = netns.bind(host, 5000, type=socket.SOCK_STREAM, timeout=10)
        with socket.socket(fileno=fd) as server_sock:
            assert server_sock.family == family
            server_sock.listen(0)

            _, fd = netns.connect(host, 5000, type=socket.SOCK_STREAM, timeout=10)
            with socket.socket(fileno=fd) as client_sock:
                c, addr = server_sock.accept()

                client_sock.send(b"Hello")
                assert c.recv(1024) == b"Hello"

                c.send(b"World")
                assert client_sock.recv(1024) == b"World"

        # Test UDP
        _, fd = netns.bind(host, 5000, type=socket.SOCK_DGRAM, timeout=10)
        with socket.socket(fileno=fd) as server_sock:
            assert server_sock.family == family

            # Test connected UDP client socket
            _, fd = netns.connect(host, 5000, type=socket.SOCK_DGRAM, timeout=10)
            with socket.socket(fileno=fd) as client_sock:
                client_sock.send(b"Hello")
                data, addr = server_sock.recvfrom(1024)
                assert data == b"Hello"

                server_sock.sendto(b"World", addr)
                data, addr = client_sock.recvfrom(1024)
                assert data == b"World"


            # Test unconnected UDP client socket
            server_addr = server_sock.getsockname()

            _, fd = netns.create_socket(server_sock.family, type=socket.SOCK_DGRAM)
            with socket.socket(fileno=fd) as client_sock:
                client_sock.sendto(b"Hello", server_addr)
                data, addr = server_sock.recvfrom(1024)
                assert data == b"Hello"

                server_sock.sendto(b"World", addr)
                data, addr = client_sock.recvfrom(1024)
                assert data == b"World"
