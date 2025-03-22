import fcntl
import os
import logging
import pty
import re
import select
import subprocess
import errno
from socket import socket, AF_INET, SOCK_STREAM
from contextlib import closing

import attr

from ..step import step

re_vt100 = re.compile(r"(\x1b\[|\x9b)[^@-_a-z]*[@-_a-z]|\x1b[@-_a-z]")

def get_free_port():
    """Helper function to always return an unused port."""
    with closing(socket(AF_INET, SOCK_STREAM)) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


def get_user():
    """Get the username of the current user."""
    user = os.environ.get("USER")
    if user:
        return user
    import pwd
    return pwd.getpwuid(os.getuid())[0]

def set_nonblocking(fd):
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

class ProcessRunner(subprocess.Popen):
    # pylint: disable=redefined-builtin
    def __init__(self, args, print_on_silent_log=False, input=None,
                 stdin=None, stdout=None, cwd=None, env=None,
                 loglevel=logging.DEBUG, callbacks=None):
        self.logger = logging.getLogger("Process")
        self.callbacks = callbacks or []
        self.loglevel = loglevel
        self.print_on_silent_log = print_on_silent_log
        self.input = input
        self.args = args

        self.res = []
        if stdout:
            sfd = stdout
            self.mfd = None
        else:
            self.mfd, sfd = pty.openpty()
            set_nonblocking(self.mfd)

        stdin_r = None
        self.stdin_w = None
        if self.input is not None:
            stdin_r, self.stdin_w = os.pipe()
            stdin = stdin_r
            set_nonblocking(self.stdin_w)

        super().__init__(args, stdin=stdin, stdout=sfd, stderr=sfd, bufsize=0,
                         cwd=cwd, env=env)
        self.logger.log(self.loglevel, "[%d] command: %s", self.pid,
                   " ".join(args))

        if print_on_silent_log and self.logger.getEffectiveLevel() > loglevel:
            processwrapper.enable_print()

        if stdin_r is not None:
            os.close(stdin_r)

        # get a file object from the fd
        self.buf = b""
        self.read_fds = []
        if self.mfd:
            self.read_fds.append(self.mfd)
            # close sfd so we notice when the child is gone
            os.close(sfd)
        self.write_fds = []
        if self.stdin_w is not None:
            self.write_fds.append(self.stdin_w)

    def check(self):
        ready_r, ready_w, _ = select.select(self.read_fds, self.write_fds, [],
                                            0.1)

        if self.mfd in ready_r:
            raw = None

            try:
                raw = os.read(self.mfd, 4096)
            except BlockingIOError:
                pass
            except OSError as e:
                if e.errno == errno.EIO:
                    return True
                raise

            if raw:
                self.buf += raw
                *parts, self.buf = self.buf.split(b'\r')
                self.res.extend(parts)
                for part in parts:
                    for callback in self.callbacks:
                        callback(part, self)

        if self.stdin_w in ready_w:
            if self.input:
                amt = 0
                try:
                    amt = os.write(self.stdin_w, self.input)
                except BlockingIOError:
                    pass
                except OSError as e:
                    if e.errno == errno.EIO:
                        return True
                    raise
                self.input = self.input[amt:]

            if not self.input:
                self.write_fds.remove(self.stdin_w)
                os.close(self.stdin_w)
                self.stdin_w = None

        self.poll()
        if self.returncode is not None:
            return True
        return False

    def finish(self):
        if self.stdin_w is not None:
            os.close(self.stdin_w)

        if self.mfd:
            os.close(self.mfd)
        self.wait()
        if self.buf:
            # process incomplete line
            self.res.append(self.buf)
            if self.buf[-1] != b'\n':
                self.buf += b'\n'
            for callback in self.callbacks:
                callback(self.buf, self)

        if self.print_on_silent_log and self.logger.getEffectiveLevel() > self.loglevel:
            processwrapper.disable_print()

        if self.returncode != 0:
            raise subprocess.CalledProcessError(self.returncode, self.args,
                                                output=b'\r'.join(self.res))

    def combined_output(self, remove_cr=True):
        # this converts '\r\n' to '\n' to be more compatible to the behaviour
        # of the normal subprocess module
        return b'\n'.join([r.strip(b'\n')
                           if remove_cr else r for r in self.res])

@attr.s
class ProcessWrapper:
    callbacks = attr.ib(default=attr.Factory(list))
    loglevel = logging.DEBUG

    @step(args=['command'], result=True, tag='process')
    # pylint: disable=redefined-builtin
    def check_output(self, command, *, print_on_silent_log=False, input=None,
                     stdin=None, cwd=None, env=None):
        """Run a command and supply the output to callback functions"""
        # do not register/unregister already registered print_callback
        if ProcessWrapper.print_callback in self.callbacks:
            print_on_silent_log = False

        proc = ProcessRunner(command, print_on_silent_log, input, stdin, None,
                             cwd, env, self.loglevel, self.callbacks)

        while True:
            if proc.check():
                break

        proc.finish()

        return proc.combined_output(remove_cr=True)

    def register(self, callback):
        """Register a callback with the ProcessWrapper"""
        if callback in self.callbacks:
            return
        self.callbacks.append(callback)

    def unregister(self, callback):
        """Unregister a callback with the ProcessWrapper"""
        if callback not in self.callbacks:
            return
        self.callbacks.remove(callback)

    @staticmethod
    def log_callback(message, process):
        """Logs process output message along with its pid."""
        logger = logging.getLogger("Process")
        message = message.decode(encoding="utf-8", errors="replace").strip("\n")
        if message:
            logger.log(ProcessWrapper.loglevel, "[%d] %s", process.pid, message)

    @staticmethod
    def print_callback(message, _):
        """Prints process output message."""
        message = message.decode(encoding="utf-8", errors="replace")
        print(f"\r{message}", end='')

    def enable_logging(self):
        """Enables process output to the logging interface."""
        self.register(ProcessWrapper.log_callback)

    def disable_logging(self):
        """Disables process output logging."""
        self.unregister(ProcessWrapper.log_callback)

    def enable_print(self):
        """Enables process output to print."""
        self.register(ProcessWrapper.print_callback)

    def disable_print(self):
        """Disables process output printing."""
        self.unregister(ProcessWrapper.print_callback)


processwrapper = ProcessWrapper()
