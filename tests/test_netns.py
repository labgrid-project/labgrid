import socket
import errno
import os

import pytest

from labgrid.util.agentwrapper import AgentWrapper
from labgrid.util.netns import NetNamespace


FAMILY_PARAMS = (
    "family,host",
    [
        pytest.param(socket.AF_INET, "127.0.0.1", id="IPv4"),
        pytest.param(socket.AF_INET6, "::1", id="IPv6"),
    ],
)


@pytest.fixture
def netns():
    with AgentWrapper(None) as aw:
        netns = NetNamespace.create(aw, "be:df:8f:7a:12:db")

        links = netns.get_links()
        link_names = [link["ifname"] for link in links]
        assert netns.intf in link_names

        # Bring up lo in the namespace
        netns.run(["ip", "link", "set", "up", "dev", "lo"], check=True)

        yield netns

        # Verify that all sockets were closed in the namespace
        assert netns._agent.list_sockets() == []


@pytest.mark.parametrize(*FAMILY_PARAMS)
def test_tcp(netns, family, host):
    with netns.socket(family, socket.SOCK_STREAM) as server_sock:
        server_sock.bind((host, 5000))
        server_sock.listen(0)

        with netns.socket(family, socket.SOCK_STREAM) as client_sock:
            client_sock.connect((host, 5000))

            c, addr = server_sock.accept()
            client_sock.send(b"Hello")
            assert c.recv(1024) == b"Hello"

            c.send(b"World")
            assert client_sock.recv(1024) == b"World"


@pytest.mark.parametrize(*FAMILY_PARAMS)
def test_udp(netns, family, host):
    with netns.socket(family, socket.SOCK_DGRAM) as server_sock:
        server_sock.bind((host, 5000))
        assert server_sock.family == family

        # Test connected UDP client socket
        with netns.socket(family, socket.SOCK_DGRAM) as client_sock:
            client_sock.connect((host, 5000))
            client_sock.send(b"Hello")
            data, addr = server_sock.recvfrom(1024)
            assert data == b"Hello"

            server_sock.sendto(b"World", addr)
            data, addr = client_sock.recvfrom(1024)
            assert data == b"World"

        # Test unconnected UDP client socket
        server_addr = server_sock.getsockname()

        with netns.socket(family, socket.SOCK_DGRAM) as client_sock:
            client_sock.sendto(b"Hello", server_addr)
            data, addr = server_sock.recvfrom(1024)
            assert data == b"Hello"

            server_sock.sendto(b"World", addr)
            data, addr = client_sock.recvfrom(1024)
            assert data == b"World"


@pytest.mark.parametrize(*FAMILY_PARAMS)
def test_getaddrinfo(netns, family, host):
    # Test getaddrinfo
    for fam, socktype, proto, cannonname, sockaddr in netns.getaddrinfo(host, 5000):
        assert fam == family


def test_closed_socket(netns):
    # Test that closed sockets result in EBADF
    s = netns.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.close()
    with pytest.raises(OSError, check=lambda e: e.errno == errno.EBADF):
        s.bind(("127.0.0.1", 5000))


def test_dup(netns):
    with netns.socket(socket.AF_INET, socket.SOCK_DGRAM) as server_sock:
        server_sock.bind(("127.0.0.1", 5000))

        # Create, then close the duplicate socket. The server socket should still function
        dup_sock = server_sock.dup()
        dup_sock.close()

        with netns.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_sock:
            client_sock.connect(("127.0.0.1", 5000))
            client_sock.send(b"Hello")
            data, addr = server_sock.recvfrom(1024)
            assert data == b"Hello"

            server_sock.sendto(b"World", addr)
            data, addr = client_sock.recvfrom(1024)
            assert data == b"World"


def test_detach(netns):
    with netns.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        fd = s.detach()
    os.close(fd)

    # Verify that all sockets were removed in the namespace
    assert netns._agent.list_sockets() == []
