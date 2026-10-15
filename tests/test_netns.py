import contextlib
import errno
import os
import socket
import subprocess
import sys
import time
from shutil import which
from unittest.mock import Mock

import pytest

from labgrid.util import get_free_port
from labgrid.util.agentwrapper import AgentWrapper
from labgrid.util.netns import DefaultNetNamespace, NetNamespace


def netns_allowed():
    result = subprocess.run(["unshare", "-Umn", "true"])
    return result.returncode == 0


FAMILY_PARAMS = (
    "family,host",
    [
        pytest.param(socket.AF_INET, "127.0.0.1", id="IPv4"),
        pytest.param(socket.AF_INET6, "::1", id="IPv6"),
    ],
)


@pytest.fixture
def netns():
    if not netns_allowed():
        pytest.skip("missing user+mount+network namespace privileges")
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
    for fam, _socktype, _proto, _cannonname, _sockaddr in netns.getaddrinfo(host, 5000):
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


@pytest.mark.skipif(not which("microsocks"), reason="microsocks not available")
def test_socks(netns, tmp_path):
    # installed via requests[socks]
    pytest.importorskip("socks")

    with contextlib.ExitStack() as stack:
        (port, password) = stack.enter_context(netns.socks_proxy())

        import requests

        proxy_url = f"socks5h://labgrid:{password}@127.0.0.1:{port}"

        proxies = {"http": proxy_url, "https": proxy_url}

        session = requests.Session()
        session.proxies.update(proxies)

        tmp_file = tmp_path / "data"
        tmp_file.write_bytes(b"test\n")

        httpd = stack.enter_context(netns.Popen(["busybox", "httpd", "-f", "-h", str(tmp_path)]))
        stack.callback(lambda: httpd.terminate())

        time.sleep(1)

        response = session.get("http://127.0.0.1/data", timeout=5)
        assert response.content == b"test\n"
        assert response.status_code == 200

        response = session.get("http://127.0.0.1/missing", timeout=5)
        assert response.status_code == 404


def test_default_create():
    agentwrapper = Mock()
    netns = DefaultNetNamespace.create(agentwrapper, "be:df:8f:7a:12:db")
    assert netns.intf == "lo"
    assert netns.prefix == []
    agentwrapper.load.assert_not_called()


def test_default_links(monkeypatch):
    check_output = Mock(
        return_value=b'[{"ifname": "lo", "ifindex": 1}, {"ifname": "eth0", "ifindex": 2}]',
    )
    monkeypatch.setattr("labgrid.util.netns.processwrapper.check_output", check_output)
    netns = DefaultNetNamespace("eth0")
    assert netns.get_links()[1] == {"ifname": "eth0", "ifindex": 2}
    assert netns.ifindex() == 2
    check_output.assert_called_with(["ip", "-j", "link"])
    with pytest.raises(KeyError, match="Interface missing not found"):
        DefaultNetNamespace("missing").ifindex()


@pytest.mark.parametrize("command", [["/bin/sh", "-c", "printf default"], "printf default"])
def test_default_commands(command, tmp_path):
    netns = DefaultNetNamespace()
    result = netns.run(command, cwd=tmp_path, capture_output=True, check=True)
    assert result.stdout == b"default"
    with netns.Popen(command, cwd=tmp_path, stdout=subprocess.PIPE) as process:
        stdout, _ = process.communicate(timeout=5)
        assert stdout == b"default"
        assert process.returncode == 0


def test_default_scripts():
    netns = DefaultNetNamespace()
    script = "import sys; print(sys.argv[1])"
    result = netns.run_script(script, ["default"], capture_output=True, check=True)
    assert result.stdout == b"default\n"
    with netns.Popen_script(script, ["default"], stdout=subprocess.PIPE) as process:
        stdout, _ = process.communicate(timeout=5)
        assert stdout == b"default\n"
        assert process.returncode == 0


def test_default_command_error():
    with pytest.raises(subprocess.CalledProcessError):
        DefaultNetNamespace().run([sys.executable, "-c", "raise SystemExit(3)"], check=True)


@pytest.mark.parametrize(*FAMILY_PARAMS)
def test_default_tcp(family, host):
    netns = DefaultNetNamespace()
    with netns.socket(family, socket.SOCK_STREAM) as server_sock:
        server_sock.bind((host, 0))
        server_sock.listen()
        server_sock.settimeout(5)

        with netns.socket(family, socket.SOCK_STREAM) as client_sock:
            client_sock.settimeout(5)
            client_sock.connect(server_sock.getsockname())
            with server_sock.accept()[0] as accepted_sock:
                accepted_sock.settimeout(5)
                client_sock.sendall(b"Hello")
                assert accepted_sock.recv(1024) == b"Hello"

                accepted_sock.sendall(b"World")
                assert client_sock.recv(1024) == b"World"


@pytest.mark.parametrize(*FAMILY_PARAMS)
def test_default_udp(family, host):
    netns = DefaultNetNamespace()
    with netns.socket(family, socket.SOCK_DGRAM) as server_sock:
        server_sock.bind((host, 0))
        server_sock.settimeout(5)
        assert server_sock.family == family

        with netns.socket(family, socket.SOCK_DGRAM) as client_sock:
            client_sock.settimeout(5)
            client_sock.connect(server_sock.getsockname())
            client_sock.send(b"Hello")
            data, _ = server_sock.recvfrom(1024)
            assert data == b"Hello"

            server_sock.sendto(b"World", client_sock.getsockname())
            data, _ = client_sock.recvfrom(1024)
            assert data == b"World"

        with netns.socket(family=family, type=socket.SOCK_DGRAM) as client_sock:
            client_sock.settimeout(5)
            client_sock.sendto(b"Hello", server_sock.getsockname())
            data, addr = server_sock.recvfrom(1024)
            assert data == b"Hello"

            server_sock.sendto(b"World", addr)
            data, _ = client_sock.recvfrom(1024)
            assert data == b"World"


@pytest.mark.parametrize(*FAMILY_PARAMS)
def test_default_getaddrinfo(family, host):
    args = (host, 5000)
    kwargs = {"family": family, "type": socket.SOCK_STREAM}
    assert DefaultNetNamespace().getaddrinfo(*args, **kwargs) == socket.getaddrinfo(*args, **kwargs)


def test_default_closed_socket():
    netns = DefaultNetNamespace()
    s = netns.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.close()
    with pytest.raises(OSError, check=lambda e: e.errno == errno.EBADF):
        s.bind(("127.0.0.1", 5000))


def test_default_dup():
    netns = DefaultNetNamespace()
    with netns.socket(socket.AF_INET, socket.SOCK_DGRAM) as server_sock:
        server_sock.bind(("127.0.0.1", 0))
        server_sock.settimeout(5)

        # Closing the duplicate must leave the original socket usable.
        with server_sock.dup() as duplicate:
            assert duplicate.getsockname() == server_sock.getsockname()

        with netns.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_sock:
            client_sock.settimeout(5)
            client_sock.connect(server_sock.getsockname())
            client_sock.send(b"Hello")
            data, addr = server_sock.recvfrom(1024)
            assert data == b"Hello"

            server_sock.sendto(b"World", addr)
            data, _ = client_sock.recvfrom(1024)
            assert data == b"World"


def test_default_detach():
    netns = DefaultNetNamespace()
    with netns.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        fd = sock.detach()
        assert sock.fileno() == -1
    os.close(fd)


@pytest.mark.skipif(not which("microsocks"), reason="microsocks not available")
def test_default_socks(tmp_path):
    pytest.importorskip("socks")

    netns = DefaultNetNamespace()
    with contextlib.ExitStack() as stack:
        port, password = stack.enter_context(netns.socks_proxy())

        import requests

        proxy_url = f"socks5h://labgrid:{password}@127.0.0.1:{port}"
        session = requests.Session()
        session.proxies.update({"http": proxy_url, "https": proxy_url})

        tmp_file = tmp_path / "data"
        tmp_file.write_bytes(b"test\n")

        http_port = get_free_port()
        httpd = stack.enter_context(
            netns.Popen(
                [
                    "busybox",
                    "httpd",
                    "-f",
                    "-p",
                    f"127.0.0.1:{http_port}",
                    "-h",
                    str(tmp_path),
                ]
            )
        )
        stack.callback(httpd.terminate)

        time.sleep(1)
        base_url = f"http://127.0.0.1:{http_port}"
        response = session.get(f"{base_url}/data", timeout=5)
        assert response.content == b"test\n"
        assert response.status_code == 200

        response = session.get(f"{base_url}/missing", timeout=5)
        assert response.status_code == 404
