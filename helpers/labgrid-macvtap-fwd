#!/usr/bin/python3
# SPDX-License-Identifier: MIT

import fcntl
import os
import struct
import sys
import struct
import argparse
import asyncio
import logging


HEADER = struct.Struct("<H")


def open_tap(name, device="/dev/net/tun"):
    TUNSETIFF = 0x400454CA
    IFF_NO_PI = 0x1000
    O_RDWR = 0x2
    IFF_TAP = 0x0002

    flags = IFF_TAP | IFF_NO_PI
    name = name.encode()
    ifr_name = name + b"\x00" * (16 - len(name))
    ifr = struct.pack("16sH22s", ifr_name, flags, b"\x00" * 22)

    fd = os.open(device, O_RDWR)
    fcntl.ioctl(fd, TUNSETIFF, ifr)
    return fd


def open_macvtap(name):
    with open(f"/sys/class/net/{name}/ifindex") as f:
        idx = f.read().strip()
    return open_tap(name=name, device="/dev/tap" + idx)


class Pipe(object):
    def __init__(self, in_fd, out_fd):
        self.frame = b""
        self.buffer = b""
        self.read_event = asyncio.Event()
        self.write_event = asyncio.Event()
        self.eof = False
        self.loop = asyncio.get_running_loop()
        self.in_fd = in_fd
        self.out_fd = out_fd
        self.eof_handler = self.set_eof

    def _handle_eof(self):
        if self.eof_handler:
            self.eof_handler()

    def set_eof(self):
        self.eof = True
        self.read_event.set()
        self.write_event.set()

    async def stream(self):
        while not self.eof:
            self.read_event.clear()
            self.loop.add_reader(self.in_fd, self.read_in)
            while not self.frame and not self.eof:
                await self.read_event.wait()
            self.loop.remove_reader(self.in_fd)

            self.write_event.clear()
            self.loop.add_writer(self.out_fd, self.write_out)
            while (self.frame or self.buffer) and not self.eof:
                await self.write_event.wait()
            self.loop.remove_writer(self.out_fd)


class StreamToTapPipe(Pipe):
    def read_until(self, length):
        while len(self.buffer) < length:
            d = os.read(self.in_fd, length - len(self.buffer))
            if not d:
                raise BrokenPipeError()
            self.buffer += d

    def read_in(self):
        if not self.frame:
            try:
                self.read_until(HEADER.size)

                hdr = HEADER.unpack_from(self.buffer)
                self.read_until(HEADER.size + hdr[0])

                self.frame = self.buffer[HEADER.size :]
                self.buffer = b""
                logging.debug("Read %d bytes from pipe", len(self.frame))

            except BlockingIOError:
                return
            except BrokenPipeError:
                logging.debug("Read pipe is closed")
                self._handle_eof()

        self.read_event.set()

    def write_out(self):
        if self.frame:
            try:
                w = os.write(self.out_fd, self.frame)
                if not w:
                    raise BrokenPipeError()
                logging.debug("Wrote %d bytes to tap", w)
                self.frame = b""
            except BlockingIOError:
                return
            except BrokenPipeError:
                logging.debug("Tap is closed")
                self._handle_eof()

        self.write_event.set()


class TapToStreamPipe(Pipe):
    def read_in(self):
        if not self.frame:
            try:
                d = os.read(self.in_fd, 1522)
                if not d:
                    raise BrokenPipeError()
                logging.debug("Read %d bytes from tap", len(d))
                self.frame = d
            except BlockingIOError:
                return
            except BrokenPipeError:
                logging.debug("Tap is closed")
                self._handle_eof()

        self.read_event.set()

    def write_out(self):
        if not self.buffer and self.frame:
            self.buffer = HEADER.pack(len(self.frame)) + self.frame
            self.frame = b""

        while self.buffer:
            try:
                w = os.write(self.out_fd, self.buffer)
                if not w:
                    raise BrokenPipeError()
                self.buffer = self.buffer[w:]
                logging.debug("Wrote %d bytes to pipe", w)
            except BlockingIOError:
                return
            except BrokenPipeError:
                logging.debug("Write pipe is closed")
                self._handle_eof()

        self.write_event.set()


async def pipe_loop(tap_fd, out_fd, in_fd):
    loop = asyncio.get_running_loop()
    os.set_blocking(tap_fd, False)
    os.set_blocking(out_fd, False)
    os.set_blocking(in_fd, False)

    def handle_eof():
        in_to_tap.set_eof()
        tap_to_out.set_eof()

    in_to_tap = StreamToTapPipe(in_fd, tap_fd)
    tap_to_out = TapToStreamPipe(tap_fd, out_fd)

    in_to_tap.eof_handler = handle_eof
    tap_to_out.eof_handler = handle_eof

    return await asyncio.gather(in_to_tap.stream(), tap_to_out.stream())


def main():
    parser = argparse.ArgumentParser("Stream tap to stdio")
    source_group = parser.add_mutually_exclusive_group(required=True)

    source_group.add_argument("--macvtap", help="Open macvtap tap")
    source_group.add_argument("--tap", metavar="NAME", help="Open tap device NAME from /dev/net/tun")
    source_group.add_argument("--fd", type=int, help="Use FD as tap file descriptor")

    parser.add_argument("--verbose", "-v", action="count", default=-1, help="Increase verbosity")

    args = parser.parse_args()

    if args.verbose >= 1:
        level = logging.DEBUG
    elif args.verbose >= 0:
        level = logging.INFO
    else:
        level = logging.WARNING
    root = logging.getLogger()
    root.setLevel(level)
    if args.macvtap:
        tap_fd = open_macvtap(args.macvtap)
    elif args.tap:
        tap_fd = open_tap(args.tap)
    else:
        tap_fd = args.fd

    # Duplicate stdin and stdout to new file descriptors for dedicated use by
    # the stream.
    with (
        os.fdopen(os.dup(sys.stdin.fileno())) as in_f,
        os.fdopen(os.dup(sys.stdout.fileno())) as out_f,
        os.fdopen(tap_fd) as tap_f,
    ):
        # Replace stdin with devnull
        with open(os.devnull, "r+") as devnull:
            os.dup2(devnull.fileno(), sys.stdin.fileno())

        # Replace stdout with stderr
        os.dup2(sys.stderr.fileno(), sys.stdout.fileno())

        asyncio.run(pipe_loop(tap_f.fileno(), out_f.fileno(), in_f.fileno()))


if __name__ == "__main__":
    sys.exit(main())
