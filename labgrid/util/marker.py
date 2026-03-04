import random
import string
import re

from pexpect import EOF, TIMEOUT, spawn

from ..protocol import CommandProcessProtocol
from ..step import step
from ..util.readmixin import ReadMixIn


# Remove RID to avoid markers containing substrings like ERROR, FAIL, WARN, INFO or DEBUG
MARKER_POOL = tuple(c for c in string.ascii_uppercase if c not in 'RID')

def gen_marker():
    return ''.join(random.choice(MARKER_POOL) for i in range(10))


class ConsoleProcessExpect(spawn):
    """labgrid Wrapper of the pexpect module.

    This class provides pexpect functionality for the ConsoleMarkerProcess
    classes. This allows users use the expect API on the output of a process
    without needing to worry about if the console is using markers (e.g.
    ShellDriver, UBootDriver). This means that these drivers behave the same as
    drivers that directly use spawn (e.g. SSHDriver), even though they are
    using markers.
    """

    def __init__(self, process, timeout):
        "Initializes a pexpect spawn instanse with required configuration"
        super().__init__(None, timeout=timeout)
        self.process = process

    def send(self, s):
        self.process.write(s)

    def read_nonblocking(self, size=1, timeout=-1):
        return self.process.read(size, timeout)

    def sendcontrol(self, char):
        self.process.sendcontrol(char)


class ConsoleMarkerProcess(CommandProcessProtocol, ReadMixIn):
    def __init__(self, console, marker, prompt, *, encoding="utf-8", timeout=30.0, on_exit=None):
        self._console = console
        self._alive = True
        self.exitcode = None
        self._on_exit = on_exit

        # Build up the Regex to capture output from the command. The regex will
        # only capture a single character from the output, and only if the
        # current buffer doesn't start with any prefix of the output buffer
        # (using negative lookahead). Partial prefixes are anchored to then end
        # of the string so as soon as it is clear that the current first
        # character of the output buffer can't possibly be part of the output
        # marker, it will be consumed.
        partials = []
        p = ""
        for m in marker[:-1]:
            p = p + m
            partials.append(r"{}$".format(p))

        # Add the complete marker, which doesn't need to be anchored to the end
        # of the string to prevent a character from being consumed.
        partials.append(marker)
        partials.reverse()

        self._output_re = re.compile(
            r"^{}.".format("".join(r"(?!{})".format(p) for p in partials)).encode(
                encoding
            ),
            re.DOTALL,
        )

        self._prompt_re = re.compile(prompt.encode(encoding))

        self._eof_re = re.compile(
            r"^{marker}\s+(\d+)\s+.*{prompt}".format(
                marker=marker, prompt=prompt
            ).encode(encoding)
        )

        self._expect = ConsoleProcessExpect(self, timeout=timeout)

    def _handle_eof(self, code):
        self.exitcode = code
        self._alive = False
        if self._on_exit:
            self._on_exit(self)

    def read(self, size=1, timeout=-1):
        # Wait up to timeout for the first byte of data
        buf = self._read_byte(timeout)

        # Read as much remaining data as possible without blocking
        while size < 0 or len(buf) < size:
            try:
                buf = buf + self._read_byte(0)
            except (TIMEOUT, EOF):
                break

        return buf

    def _read_byte(self, timeout):
        if not self._alive:
            raise EOF("ConsoleMarkerProcess end-of-file")

        index, _, match, after = self._console.expect_no_step(
            [self._output_re, self._eof_re, TIMEOUT],
            timeout=timeout,
        )
        if index == 0:
            return after
        elif index == 1:
            self._handle_eof(int(match.group(1)))
            raise EOF("ConsoleMarkerProcess end-of-file")
        elif index == 2:
            raise TIMEOUT("ConsoleMarkerProcess timeout")

    @step(args=["data"])
    def write(self, data):
        if self._alive:
            return self._console.write(data)
        return 0

    @step(result=True)
    def poll(self):
        if not self._alive:
            return self.exitcode

        index, _, match, _ = self._console.expect([self._eof_re, TIMEOUT], timeout=1)

        if index == 0:
            self._handle_eof(int(match.group(1)))
            return self.exitcode

        return None

    @step(result=True)
    def stop(self):
        if self._alive:
            self._console.sendcontrol("c")
            # Not all shells will emit the marker and exit code on interrupt.
            # Check for a bare prompt in addition to EOF for these shells
            index, _, _, _ = self.expect([EOF, self._prompt_re], timeout=60)
            if index == 1:
                # If a prompt was seen with no marker, emulate the exit code
                # for "died by SIGINT" (130)
                self._handle_eof(130)

    @step(args=["pattern", "timeout"], result=True)
    def expect(self, pattern, *, timeout=-1):
        return (
            self._expect.expect(pattern, timeout=timeout),
            self._expect.before,
            self._expect.match,
            self._expect.after,
        )

    @step(result=True)
    def wait(self):
        while True:
            index, _, _, _ = self.expect([EOF, TIMEOUT])
            if index == 0:
                break

    @step(args=["char"])
    def sendcontrol(self, char):
        self._console.sendcontrol(char)

    def __enter__(self):
        return self

    def __exit__(self, typ, value, traceback):
        self.stop()
        return False
