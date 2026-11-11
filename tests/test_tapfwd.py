import os
import socket
import struct
import subprocess
import sys

import pytest

HEADER = struct.Struct("<H")


@pytest.fixture
def tap():
    """A datagram socket pair standing in for a tap device: each read
    returns one whole frame, as from a tap file descriptor."""
    ours, theirs = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
    yield ours, theirs
    ours.close()
    theirs.close()


def start_tapfwd(tap_fd, stdin, stdout):
    return subprocess.Popen(
        [sys.executable, "-m", "labgrid.tapfwd", str(tap_fd)],
        stdin=stdin,
        stdout=stdout,
        pass_fds=(tap_fd,),
    )


def test_forwards_frames_both_ways(tap):
    ours, theirs = tap
    in_r, in_w = os.pipe()
    out_r, out_w = os.pipe()
    with start_tapfwd(theirs.fileno(), in_r, out_w) as fwd:
        os.close(in_r)
        os.close(out_w)

        ours.send(b"from the tap")
        assert os.read(out_r, 100) == HEADER.pack(12) + b"from the tap"

        os.write(in_w, HEADER.pack(14) + b"from the pipe!")
        assert ours.recv(100) == b"from the pipe!"

        os.close(in_w)
        assert fwd.wait(timeout=10) == 0
    os.close(out_r)


def test_exits_when_the_output_pipe_closes_with_a_frame_pending(tap):
    ours, theirs = tap
    in_r, in_w = os.pipe()
    out_r, out_w = os.pipe()
    os.close(out_r)
    ours.send(b"a frame nobody reads")
    with start_tapfwd(theirs.fileno(), in_r, out_w) as fwd:
        os.close(in_r)
        os.close(out_w)
        try:
            assert fwd.wait(timeout=10) == 0
        finally:
            fwd.kill()
            os.close(in_w)
