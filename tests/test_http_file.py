from concurrent.futures import ThreadPoolExecutor
import gzip
from http.client import HTTPConnection, RemoteDisconnected
import shutil
import socket
import subprocess
import threading
import time

import pytest

from labgrid.util import http as http_file
from labgrid.util.http import serve_file


@pytest.fixture
def image(tmp_path):
    path = tmp_path / 'image with spaces.wic'
    path.write_bytes(b'0123456789')
    return path


@pytest.fixture
def server(image):
    with serve_file(image) as address:
        yield address


def request(server, method='GET', headers=None, path=None):
    port, image_path = server
    connection = HTTPConnection('127.0.0.1', port, timeout=5)
    try:
        connection.request(method, path or image_path, headers=headers or {})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


@pytest.mark.parametrize('range_value,status,body,content_range', [
    (None, 200, b'0123456789', None),
    ('bytes=2-5', 206, b'2345', 'bytes 2-5/10'),
    ('bytes=7-', 206, b'789', 'bytes 7-9/10'),
    ('bytes=-3', 206, b'789', 'bytes 7-9/10'),
    ('bytes=-30', 206, b'0123456789', 'bytes 0-9/10'),
    ('bytes=8-99', 206, b'89', 'bytes 8-9/10'),
    ('bytes=10-', 416, b'', 'bytes */10'),
    ('bytes=-0', 416, b'', 'bytes */10'),
    ('bytes=4-2', 200, b'0123456789', None),
    ('bytes=garbage', 200, b'0123456789', None),
    ('bytes=0-1,4-5', 200, b'0123456789', None),
])
def test_ranges(server, range_value, status, body, content_range):
    headers = {'Range': range_value} if range_value else {}
    actual_status, actual_headers, actual_body = request(server, headers=headers)

    assert actual_status == status
    assert actual_body == body
    assert actual_headers['Content-Length'] == str(len(body))
    assert actual_headers.get('Content-Range') == content_range


def test_head_ignores_range(server):
    status, headers, body = request(server, 'HEAD', {'Range': 'bytes=2-5'})

    assert status == 200
    assert headers['Content-Length'] == '10'
    assert headers['Accept-Ranges'] == 'bytes'
    assert body == b''


def test_if_range_returns_full_file(server):
    status, _, body = request(server, headers={'Range': 'bytes=2-5', 'If-Range': '"old"'})
    assert status == 200
    assert body == b'0123456789'


@pytest.mark.parametrize('path', ['/', '/image with spaces.wic'.replace(' ', '%20'), '/../../etc/passwd'])
def test_only_selected_url_is_accessible(server, path):
    assert request(server, path=path)[0] == 404


def test_empty_file(image):
    image.write_bytes(b'')
    with serve_file(image) as server:
        assert request(server)[2] == b''
        assert request(server, headers={'Range': 'bytes=0-'})[0] == 416


def test_concurrent_ranges(server):
    with ThreadPoolExecutor(max_workers=4) as executor:
        responses = list(executor.map(
            lambda _: request(server, headers={'Range': 'bytes=2-5'}), range(8)
        ))
    assert all(status == 206 and body == b'2345' for status, _, body in responses)


def test_range_crosses_transfer_chunk_boundary(image):
    content = bytes(range(256)) * 8192
    image.write_bytes(content)
    with serve_file(image) as server:
        status, headers, body = request(server, headers={'Range': 'bytes=17-1500000'})
    assert status == 206
    assert body == content[17:1500001]
    assert int(headers['Content-Length']) == len(body)


def test_client_disconnect_does_not_stop_server(image):
    image.write_bytes(b'x' * (8 * 1024 * 1024))
    with serve_file(image) as server:
        port, path = server
        with socket.create_connection(('127.0.0.1', port), timeout=5) as client:
            client.sendall(f'GET {path} HTTP/1.0\r\n\r\n'.encode())
            assert client.recv(1024)
        status, _, body = request(server, headers={'Range': 'bytes=0-3'})
        assert status == 206
        assert body == b'xxxx'


def test_slow_consumer_receives_entire_image(image):
    content = bytes(range(256)) * (128 * 1024)
    image.write_bytes(content)
    with serve_file(image) as (port, path):
        connection = HTTPConnection('127.0.0.1', port, timeout=10)
        try:
            connection.request('GET', path)
            response = connection.getresponse()
            # Exceed the former response-write timeout while the large response
            # fills the socket buffers and blocks the server's writer.
            time.sleep(6)
            assert response.read() == content
        finally:
            connection.close()


@pytest.mark.parametrize('complete_headers', [False, True], ids=['headers', 'body'])
def test_shutdown_interrupts_active_connections(image, complete_headers):
    image.write_bytes(b'x' * (32 * 1024 * 1024))
    with ThreadPoolExecutor(max_workers=1) as executor:
        context = serve_file(image)
        port, path = context.__enter__()
        client = socket.create_connection(('127.0.0.1', port), timeout=5)
        shutdown = None
        try:
            if complete_headers:
                client.sendall(f'GET {path} HTTP/1.0\r\n\r\n'.encode())
                assert client.recv(1024)
            else:
                client.sendall(b'GET / HTTP/1.0\r\nX: ')
                # A second request confirms the server has accepted the first.
                assert request((port, path), method='HEAD')[0] == 200
            shutdown = executor.submit(context.__exit__, None, None, None)
            shutdown.result(timeout=2)
        finally:
            client.close()
            if shutdown is None:
                context.__exit__(None, None, None)
            else:
                shutdown.result(timeout=10)


def test_connection_limit_rejects_excess_and_recovers(image, monkeypatch):
    monkeypatch.setattr(http_file, '_MAX_CONNECTIONS', 1)
    with serve_file(image) as server:
        port, path = server
        with socket.create_connection(('127.0.0.1', port), timeout=2) as client:
            client.sendall(f'GET {path} HTTP/1.0\r\nX: '.encode())
            # Accepts are ordered: this request must be refused while the first
            # connection occupies the only handler slot.
            with pytest.raises((RemoteDisconnected, ConnectionResetError)):
                request(server)
            client.sendall(b'done\r\n\r\n')
            response = bytearray()
            while chunk := client.recv(4096):
                response.extend(chunk)
            assert response.endswith(b'0123456789')
        # EOF above confirms close_request has released the slot.
        assert request(server)[0] == 200


@pytest.mark.parametrize('prefix', [b'GET /', b'GET / HTTP/1.0\r\nX: '],
                         ids=['request-line', 'headers'])
def test_header_deadline_closes_dripping_requests(image, monkeypatch, prefix):
    monkeypatch.setattr(http_file, '_HEADER_TIMEOUT', 0.3)
    with serve_file(image) as server:
        port, _ = server
        with socket.create_connection(('127.0.0.1', port), timeout=2) as client:
            client.sendall(prefix)
            stopped = threading.Event()
            sent = []

            def drip():
                while not stopped.wait(0.02):
                    try:
                        client.sendall(b'x')
                        sent.append(True)
                    except OSError:
                        return

            thread = threading.Thread(target=drip)
            thread.start()
            try:
                assert client.recv(4096) == b''
                assert len(sent) >= 2
            finally:
                stopped.set()
                thread.join(timeout=2)
            assert not thread.is_alive()
        assert request(server)[0] == 200


def test_shutdown_on_error(image):
    with pytest.raises(RuntimeError, match='write failed'):
        with serve_file(image) as server:
            assert request(server)[0] == 200
            raise RuntimeError('write failed')
    with pytest.raises(OSError):
        request(server)


@pytest.mark.skipif(shutil.which('bmaptool') is None, reason='bmaptool is not installed')
@pytest.mark.parametrize('compressed', [False, True])
def test_bmaptool_http_copy(tmp_path, compressed):
    image = tmp_path / 'image.wic'
    image.write_bytes(b'labgrid' * 4096)
    bmap = tmp_path / 'image.bmap'
    output = tmp_path / 'output.wic'
    subprocess.run(['bmaptool', 'create', '-o', str(bmap), str(image)], check=True)

    source = image
    if compressed:
        source = tmp_path / 'image.wic.gz'
        source.write_bytes(gzip.compress(image.read_bytes()))

    with serve_file(source) as (port, path):
        subprocess.run([
            'bmaptool', 'copy', '--bmap', str(bmap),
            f'http://127.0.0.1:{port}{path}', str(output),
        ], check=True, timeout=30)

    assert output.read_bytes() == image.read_bytes()
