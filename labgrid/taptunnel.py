#! /usr/bin/env python3

import os
import struct
import fcntl
import sys
import argparse
import asyncio
import logging
from abc import ABC, abstractmethod
import zlib
from contextlib import contextmanager


MAX_PACKET_SIZE = 1 * 1024 * 1024


@contextmanager
def create_tap(name, device):
    TUNSETIFF = 0x400454CA
    IFF_TAP = 0x0002
    IFF_NO_PI = 0x1000

    with os.fdopen(os.open(device, os.O_RDWR)) as fd:
        ifr = struct.pack("16sH22s", name.encode("utf-8"), IFF_TAP | IFF_NO_PI, b"\x00" * 22)
        fcntl.ioctl(fd, TUNSETIFF, ifr)
        yield TapStream(fd.fileno())


class ReadyFD(object):
    def __init__(self, fd):
        self.fd = fd

    def close(self):
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def signal(self):
        if self.fd >= 0:
            os.write(self.fd, b"1")
            self.close()


class Stream(ABC):
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    async def stream_to(self, dest):
        async for data in self:
            await dest.send(data)

    async def stream(self, dest):
        await asyncio.gather(self.stream_to(dest), dest.stream_to(self))

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            data = await self.recv()
            if not data:
                raise StopAsyncIteration
        except EOFError:
            raise StopAsyncIteration
        return data

    @abstractmethod
    async def send(self, data):
        raise NotImplementedError("Must be implemented in derived classes")

    @abstractmethod
    async def recv(self):
        raise NotImplementedError("Must be implemented in derived classes")


class TapStream(Stream):
    def __init__(self, fd):
        super().__init__()
        self.fd = fd
        os.set_blocking(self.fd, False)

        self.read_buf = None
        self.read_lock = asyncio.Lock()
        self.read_event = asyncio.Event()

        self.write_buf = None
        self.write_lock = asyncio.Lock()
        self.write_event = asyncio.Event()

        self.loop = asyncio.get_running_loop()

    def __do_read(self):
        if not self.read_buf:
            try:
                self.read_buf = os.read(self.fd, MAX_PACKET_SIZE)
            except BlockingIOError:
                self.logger.debug("Would block on read")
                return

        self.read_event.set()

    def __do_write(self):
        if self.write_buf:
            try:
                os.write(self.fd, self.write_buf)
            except BlockingIOError:
                self.logger.debug("Would block on write")
                return

            self.logger.debug("Wrote %d bytes", len(self.write_buf))
            self.write_buf = None

        self.write_event.set()

    async def send(self, data):
        async with self.write_lock:
            hdr = struct.unpack_from("@hh", data)
            self.logger.debug("Writing %d bytes: %s", len(data), hdr)

            self.write_buf = data

            self.loop.add_writer(self.fd, self.__do_write)
            try:
                while self.write_buf:
                    await self.write_event.wait()
                    self.write_event.clear()
            finally:
                self.loop.remove_writer(self.fd)

    async def recv(self):
        async with self.read_lock:
            self.loop.add_reader(self.fd, self.__do_read)
            try:
                while not self.read_buf:
                    await self.read_event.wait()
                    self.read_event.clear()
            finally:
                self.loop.remove_reader(self.fd)

            data = self.read_buf
            self.read_buf = None
            # data = struct.pack(">hh", *hdr) + self.read_buf[4:]

        hdr = struct.unpack_from("@hh", data)
        self.logger.debug("Got %d bytes: %s", len(data), hdr)
        return data


class ProtocolError(Exception):
    pass


class ProtocolStream(Stream):
    MAGIC = b"TAPT\x01"

    HEADER_FORMAT = "<LL"
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

    @classmethod
    async def connect(cls, *args, **kwargs):
        s = cls(*args, **kwargs)
        s.write(cls.MAGIC)
        _, remote_magic = await asyncio.gather(s.drain(), s.read(len(cls.MAGIC)))
        if remote_magic != cls.MAGIC:
            raise ProtocolError(f"Bad magic from remote. Got {remote_magic}, expected {cls.MAGIC}")
        logging.debug("Verified remote magic: %s", remote_magic)
        return s

    @abstractmethod
    async def read(self, size):
        raise NotImplementedError("Must be implemented in derived classes")

    @abstractmethod
    def write(self, data):
        raise NotImplementedError("Must be implemented in derived classes")

    @abstractmethod
    async def drain(self):
        raise NotImplementedError("Must be implemented in derived classes")

    async def send(self, data):
        self.write(struct.pack(self.HEADER_FORMAT, len(data), zlib.crc32(data)))
        self.write(data)
        await self.drain()
        self.logger.debug("Sent %d bytes", len(data))

    async def recv(self):
        hdr = struct.unpack(self.HEADER_FORMAT, await self.read(self.HEADER_SIZE))
        data = await self.read(hdr[0])
        exp_crc = zlib.crc32(data)
        if exp_crc != hdr[1]:
            raise ProtocolError("Invalid CRC. Expected %d, got %d", exp_crc, hdr[1])
        self.logger.debug("Received %d bytes", len(data))
        return data


class FDStream(ProtocolStream):
    def __init__(self, in_fd, out_fd):
        super().__init__()
        self.in_fd = in_fd
        self.out_fd = out_fd

        os.set_blocking(self.in_fd, False)
        os.set_blocking(self.out_fd, False)

        self._eof = False

        self._read_buf = b""
        self._read_lock = asyncio.Lock()
        self._read_event = asyncio.Event()

        self._write_buf = b""
        self._write_lock = asyncio.Lock()
        self._write_event = asyncio.Event()

        self.loop = asyncio.get_running_loop()

    def _set_eof(self):
        if not self._eof:
            logging.info("Got EOF")
            self._eof = True

    def __do_read(self):
        try:
            data = os.read(self.in_fd, 1024)
        except BlockingIOError:
            self.logger.debug("Would block on read")
            return
        except BrokenPipeError:
            self._set_eof()
            self._read_event.set()
            return

        if not data:
            self._set_eof()
        else:
            self._read_buf += data
        self._read_event.set()

    def __do_write(self):
        if self._write_buf:
            try:
                w = os.write(self.out_fd, self._write_buf)
            except BlockingIOError:
                self.logger.debug("Would block on write")
                return
            except BrokenPipeError:
                self._set_eof()
                self._write_event.set()
                return

            if w == 0:
                self._set_eof()
            else:
                self._write_buf = self._write_buf[w:]

        self._write_event.set()

    async def read(self, size):
        async with self._read_lock:
            self.loop.add_reader(self.in_fd, self.__do_read)
            try:
                while len(self._read_buf) < size:
                    if self._eof:
                        raise EOFError()
                    await self._read_event.wait()
                    self._read_event.clear()
            finally:
                self.loop.remove_reader(self.in_fd)

            data = self._read_buf[:size]
            self._read_buf = self._read_buf[size:]

        return data

    def write(self, data):
        self._write_buf += data

    async def drain(self):
        async with self._write_lock:
            self.loop.add_writer(self.out_fd, self.__do_write)
            try:
                while self._write_buf:
                    if self._eof:
                        raise EOFError()
                    await self._write_event.wait()
                    self._write_event.clear()
            finally:
                self.loop.remove_writer(self.out_fd)


async def stdio_stream(args, tap, ready):
    # Duplicate stdin and stdout to new file descriptors for dedicated use by
    # the stream. Replace the normal stdin and stdout descriptors with
    # /dev/null to prevent errant output from corrupting the stream
    with os.fdopen(os.dup(sys.stdin.fileno())) as in_fd, os.fdopen(os.dup(sys.stdout.fileno())) as out_fd:
        with open(os.devnull, "r+") as devnull:
            os.dup2(devnull.fileno(), sys.stdin.fileno())
        os.dup2(sys.stderr.fileno(), sys.stdout.fileno())

        ready.signal()

        logging.debug("In FD is %d", in_fd.fileno())
        logging.debug("Out FD is %d", out_fd.fileno())

        s = await FDStream.connect(in_fd.fileno(), out_fd.fileno())

        await asyncio.gather(s.stream(tap))
    return 0


async def amain():
    parser = argparse.ArgumentParser(description="Tunnel TAP data")

    parser.add_argument("--device", "-d", help="TUN device", default="/dev/net/tun")
    parser.add_argument("--tap-name", "-t", help="TAP name", default="tap0")

    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=-1,
        help="Increase verbosity",
    )
    parser.add_argument(
        "--ready-fd",
        type=int,
        default=-1,
        help="Ready signal file descriptor",
    )

    args = parser.parse_args()

    if args.verbose >= 1:
        level = logging.DEBUG
    elif args.verbose >= 0:
        level = logging.INFO
    else:
        level = logging.WARNING
    root = logging.getLogger()
    root.setLevel(level)

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)
    formatter = logging.Formatter(f"{os.getpid()}: %(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    root.addHandler(handler)

    with create_tap(args.tap_name, args.device) as t, ReadyFD(args.ready_fd) as ready:
        logging.debug("TAP is FD %d", t.fd)
        return await stdio_stream(args, t, ready)

    return 0


def main():
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
