import os
import re
import secrets
import socket
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote


_MAX_CONNECTIONS = 16
_HEADER_TIMEOUT = 5


@contextmanager
def serve_file(filename):
    """Serve one file over loopback HTTP for the duration of the context."""
    filename = os.path.realpath(filename)
    # Keep the suffix for consumers which detect compression from the URL.
    path = f"/{secrets.token_urlsafe(24)}/{quote(os.path.basename(filename))}"

    stopping = threading.Event()
    connections = {}
    connections_lock = threading.Lock()

    class Server(ThreadingHTTPServer):
        def verify_request(self, connection, address):
            with connections_lock:
                if len(connections) >= _MAX_CONNECTIONS:
                    return False
                connections[connection] = time.monotonic() + _HEADER_TIMEOUT
                return True

        def service_actions(self):
            # Enforce a total header deadline, not just an inactivity timeout.
            with connections_lock:
                now = time.monotonic()
                for connection, deadline in connections.items():
                    if deadline is not None and now >= deadline:
                        try:
                            connection.shutdown(socket.SHUT_RDWR)
                        except OSError:
                            pass

        def close_request(self, connection):
            with connections_lock:
                connections.pop(connection, None)
                super().close_request(connection)

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(_HEADER_TIMEOUT)

        def parse_request(self):
            parsed = super().parse_request()
            # HTTP/1.0 responses close each connection; there is no subsequent
            # keep-alive request whose headers need another deadline.
            with connections_lock:
                if time.monotonic() >= connections[self.connection]:
                    return False
                connections[self.connection] = None
            return parsed

        def log_message(self, format, *args):
            pass

        def do_HEAD(self):
            self.respond(False)

        def do_GET(self):
            self.respond(True)

        def respond(self, body):
            # Storage writes can pause consumption indefinitely. Teardown interrupts
            # active sockets explicitly rather than timing out response writes.
            self.connection.settimeout(None)
            if self.path != path:
                self.send_error(404)
                return
            try:
                source = open(filename, 'rb')
            except OSError:
                self.send_error(404)
                return
            with source:
                size = os.fstat(source.fileno()).st_size
                start, end = 0, size - 1
                status = 200
                # Range applies only to GET. Ignore unsupported/malformed ranges
                # and If-Range requests (we do not advertise validators).
                value = self.headers.get('Range', '') if body else ''
                match = re.fullmatch(r'bytes=([0-9]{0,20})-([0-9]{0,20})', value)
                if match and any(match.groups()) and 'If-Range' not in self.headers:
                    first, last = match.groups()
                    if first:
                        start = int(first)
                        end = min(int(last), size - 1) if last else size - 1
                        if last and int(last) < start:
                            start, end = 0, size - 1  # malformed: ignore
                        else:
                            status = 206
                    else:
                        start = max(0, size - int(last))
                        status = 206
                    if status == 206 and (start >= size or end < start):
                        self.send_response(416)
                        self.send_header('Content-Range', f'bytes */{size}')
                        self.send_header('Content-Length', '0')
                        self.end_headers()
                        return
                length = max(0, end - start + 1)
                self.send_response(status)
                self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('Accept-Ranges', 'bytes')
                self.send_header('Content-Length', str(length))
                if status == 206:
                    self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
                self.end_headers()
                if not body:
                    return
                source.seek(start)
                try:
                    while length and not stopping.is_set():
                        chunk = source.read(min(length, 1024 * 1024))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        length -= len(chunk)
                except (BrokenPipeError, ConnectionResetError, TimeoutError):
                    pass

    with Server(('127.0.0.1', 0), Handler) as server:
        server.daemon_threads = False
        # Bound shutdown latency without the default half-second polling delay.
        thread = threading.Thread(
            target=server.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True
        )
        thread.start()
        try:
            yield server.server_port, path
        finally:
            stopping.set()
            server.shutdown()
            thread.join()
            # No more connections can be accepted. Interrupt both blocked writes
            # and incomplete request headers before server_close joins handlers.
            with connections_lock:
                for connection in connections:
                    try:
                        connection.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
