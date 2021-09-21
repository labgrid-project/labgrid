import fcntl
import logging
import os
import select
import shlex
import subprocess

import attr

from ..factory import target_factory
from ..protocol import ConsoleProtocol
from .common import Driver
from .consoleexpectmixin import ConsoleExpectMixin
from .exception import ExecutionError


@target_factory.reg_driver
@attr.s(eq=False)
class ExternalConsoleDriver(ConsoleExpectMixin, Driver, ConsoleProtocol):
    """
    Driver implementing the ConsoleProtocol interface using a subprocess
    """
    cmd = attr.ib(validator=attr.validators.instance_of(str))
    txdelay = attr.ib(default=0.0, validator=attr.validators.instance_of(float))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.logger = logging.getLogger(f"{self}({self.target})")
        self.status = 0  #pylint: disable=attribute-defined-outside-init
        self._child = None
        self.open()

    def open(self):
        """Starts the subprocess, does nothing if it is already closed"""
        if self.status:
            return
        cmd = shlex.split(self.cmd)
        self._child = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None
        )

        # make stdout non-blocking
        stdout_fd = self._child.stdout.fileno()
        stdout_fl = fcntl.fcntl(stdout_fd, fcntl.F_GETFL) | os.O_NONBLOCK
        fcntl.fcntl(stdout_fd, fcntl.F_SETFL, stdout_fl)

        # prepare for timeout handing
        self._poll = select.poll()
        self._poll.register(self._child.stdout.fileno())
        self.status = 1

    def close(self):
        """Stops the subprocess, does nothing if it is already closed"""
        if not self.status:
            return
        if self._child.poll() is not None:
            raise ExecutionError("child has vanished")
        self._child.terminate()
        try:
            outs, errs = self._child.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            self._child.kill()
            outs, errs = self._child.communicate()

        if outs:
            self.logger.info("child stdout while closing: %s", outs)
        if errs:
            self.logger.warning("child error while closing: %s", errs)

        self._child = None
        self.status = 0

    def _read(self, size: int = 1024, timeout: int = 0):
        """
        Reads 'size' bytes from the serialport

        Keyword Arguments:
        size -- amount of bytes to read, defaults to 1024
        """
        if self._child.poll() is not None:
            raise ExecutionError("child has vanished")
        if self._poll.poll(timeout):
            return self._child.stdout.read(size)

        return b''

    def _write(self, data: bytes):
        """
        Writes 'data' to the serialport

        Arguments:
        data -- data to write, must be bytes
        """
        if self._child.poll() is not None:
            raise ExecutionError("child has vanished")
        result = self._child.stdin.write(data)
        self._child.stdin.flush()
        return result

    def on_deactivate(self):
        self.close()
