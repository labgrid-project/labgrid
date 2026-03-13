import pytest
import attr
import logging
from pexpect import TIMEOUT, EOF

from labgrid.factory import target_factory
from labgrid.util import ConsoleMarkerProcess
from labgrid.protocol import ConsoleProtocol
from labgrid.driver import Driver
from labgrid.driver.consoleexpectmixin import ConsoleExpectMixin


@target_factory.reg_driver
@attr.s(eq=False)
class EchoConsoleDriver(ConsoleExpectMixin, Driver, ConsoleProtocol):
    prompt = attr.ib(validator=attr.validators.instance_of(str))
    marker = attr.ib(default="ABC", validator=attr.validators.instance_of(str))
    txdelay = attr.ib(default=0.0, validator=attr.validators.instance_of(float))
    timeout = attr.ib(default=1.0, validator=attr.validators.instance_of(float))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.logger = logging.getLogger("{}({})".format(self, self.target))
        self.buffer = b""

    def _read(self, size=-1, timeout=0.0, max_size=None):
        if not self.buffer:
            raise TIMEOUT("Timeout reading data")
        elif size < 0 or size >= len(self.buffer):
            data = self.buffer
            self.buffer = b""
        else:
            data = self.buffer[:size]
            self.buffer = self.buffer[size:]
        print("READ: %r %r" % (data, self.buffer))
        return data

    def _write(self, data, *_):
        if b"\x03" in data:
            a, b = data.split(b"\x03", 1)
            self.buffer = self.buffer + a + self._end_process_string(-1) + b
        else:
            self.buffer = self.buffer + data
        print("WRITE: %r" % self.buffer)

    def _end_process_string(self, retcode):
        return "{}\n{}\n{}".format(self.marker, retcode, self.prompt).encode("utf-8")

    def open(self):
        pass

    def close(self):
        pass

    def end_process(self, retcode):
        self.buffer = self.buffer + self._end_process_string(retcode)


@pytest.fixture(scope="function")
def console(target):
    d = EchoConsoleDriver(target, "console", prompt="PROMPT>")
    target.activate(d)
    return d


@pytest.fixture(scope="function")
def process(console):
    return ConsoleMarkerProcess(console, console.marker, console.prompt, timeout=0.1)


def test_create(console):
    ConsoleMarkerProcess(console, console.marker, console.prompt)


def test_partial_read(console, process):
    process.write(b"Hello World")
    console.end_process(0)

    assert process.read_full(6, timeout=0.1) == b"Hello "
    assert process.poll() is None

    assert process.read_full(5) == b"World"
    assert process.poll() == 0

    assert process.read_full(1, timeout=0.1) == b""
    with pytest.raises(EOF):
        process.read(1)


def test_read_timeout(console, process):
    process.write(b"Hello World")

    assert process.read_full(100, timeout=0.1) == b"Hello World"

    process.read_full(100, timeout=0.1) == b""

    with pytest.raises(TIMEOUT):
        process.read(100)

    process.write(b"Hello World")

    with pytest.raises(TIMEOUT):
        process.expect("Never found", timeout=0.1)


def test_expect(console, process):
    process.write(b"Hello World")
    console.end_process(0)

    index, before, match, after = process.expect([b"Hello", "World"], timeout=0.1)
    assert index == 0
    assert before == b""
    assert match.group(0) == b"Hello"
    assert after == b"Hello"

    index, before, match, after = process.expect([b"Hello", "World"], timeout=0.1)
    assert index == 1
    assert before == b" "
    assert match.group(0) == b"World"
    assert after == b"World"

    with pytest.raises(EOF):
        process.expect([b"Hello", "World"], timeout=0.1)

    index, before, match, after = process.expect([r"Hello", r"World", EOF], timeout=0.1)
    assert index == 2
    assert before == b""


def test_marker(console, process):
    for i in range(len(console.marker) - 1):
        partial_marker = console.marker[: i + 1].encode("utf-8")
        process.write(partial_marker)
        # Any match on a partial marker should not consume any output until we
        # are certain it's not actually a marker
        assert process.read_full(100, timeout=0.1) == b""

        with pytest.raises(TIMEOUT):
            process.read(100)

        with pytest.raises(TIMEOUT):
            process.expect(r".+", timeout=0.1)

        assert process.expect([r".+", TIMEOUT], timeout=0.1) == (1, b"", TIMEOUT, TIMEOUT)

        # Write the partial marker again, which means the original partial can
        # be returned since it is guaranteed to not be a match for the complete
        # marker
        process.write(partial_marker)
        assert process.read_full(100, timeout=0.1) == partial_marker

        # Do it again for read_nonblocking
        process.write(partial_marker)
        assert process.read(100) == partial_marker

        # Do it again for expect
        process.write(partial_marker)
        index, before, match, after = process.expect([r".+"], timeout=0.1)
        assert index == 0
        assert before == b""
        assert match.group(0) == partial_marker
        assert after == partial_marker

        # Write a space, which makes the last partial no longer match the marker
        process.write(b" ")
        assert process.read_full(100, timeout=0.1) == partial_marker + b" "


def test_read_to_end(console, process):
    process.write(b"Hello World")
    console.end_process(0)

    process.read_to_end() == b"Hello World"
    process.read_to_end() == b""


def test_read_to_end_timeout(console, process):
    process.write(b"Hello World")
    with pytest.raises(TIMEOUT):
        process.read_to_end(timeout=0.1)

    console.end_process(0)
    assert process.read_to_end() == b""


def test_read_exact(console, process):
    process.write(b"Hello World")
    assert process.read_exact(6) == b"Hello "
    process.write(b" Exact")
    assert process.read_exact(11) == b"World Exact"

    with pytest.raises(TIMEOUT):
        process.read_exact(1)

    console.end_process(0)

    with pytest.raises(EOF):
        process.read_exact(1)
