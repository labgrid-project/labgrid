from pexpect import EOF, TIMEOUT
from .timeout import Timeout

class ReadMixIn:
    """
    This class make it more convenient to deal with reading from devices. A
    typical read() will either return immediately if there is buffered data, or
    wait up to some timeout for data to appear, then return whatever happens to
    be buffered at that time. In both of these cases, less data that requested
    may be returned before the timeout expires, even if no EOF is encountered.

    The function in this class help deal with sources like this by trying harder
    to read data from the device.

    Inspired by the function of the same name present in Rust
    """
    def read(self, size, timeout):
        """
        Stub for mixin. Must be implemented by subclass.
        """
        raise NotImplementedError

    def read_full(self, size=-1, *, timeout=30):
        """
        Reads bytes until either size bytes have been read, timeout seconds
        have elapsed, or EOF is encountered. Returns as many bytes as were read
        until that happens.

        If size is -1, read as much data as possible until either the timeout
        or EOF is encountered.
        """
        t = Timeout(timeout)
        buf = b""

        while not t.expired:
            read_size = size - len(buf) if size >= 0 else 64
            if read_size <= 0:
                break

            try:
                buf += self.read(read_size, t.remaining)
            except EOF:
                break
            except TIMEOUT:
                pass

        return buf

    def read_to_end(self, *, timeout=30):
        """
        Read until EOF is encountered and return the resulting data. If the
        timeout expires before EOF, a TIMEOUT error is raised

        If an exception is raised, any data read is lost
        """
        t = Timeout(timeout)
        buf = b""

        while True:
            try:
                buf += self.read(64, t.remaining)
            except EOF:
                break

        return buf

    def read_exact(self, size, *, timeout=30):
        """
        Read exactly size bytes. If the timeout elapses before size bytes are
        read, a TIMEOUT error is raised. If EOF is encountered before size
        bytes are read, an EOF error is raised

        If an exception is raised, any data read is lost
        """
        t = Timeout(timeout)
        buf = b""

        while len(buf) < size:
            buf += self.read(size - len(buf), t.remaining)

        return buf
