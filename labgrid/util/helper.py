import fcntl
import os
import logging
import pty
import select
import subprocess
from socket import socket, AF_INET, SOCK_STREAM
from contextlib import closing

import attr

from ..step import step

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

@attr.s
class ProcessWrapper:
    callbacks = attr.ib(default=attr.Factory(list))
    loglevel = logging.INFO

    @step(args=['command'], result=True, tag='process')
    def check_output(self, command, *, print_on_silent_log=False):
        """Run a command and supply the output to callback functions"""
        logger = logging.getLogger("Process")
        res = []
        mfd, sfd = pty.openpty()
        flags = fcntl.fcntl(mfd, fcntl.F_GETFL)
        fcntl.fcntl(mfd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        process = subprocess.Popen(command, stderr=sfd,
                                   stdout=sfd, bufsize=0)

        logger.log(ProcessWrapper.loglevel, "[%d] command: %s", process.pid, " ".join(command))

        # do not register/unregister already registered print_callback
        if ProcessWrapper.print_callback in self.callbacks:
            print_on_silent_log = False

        if print_on_silent_log and logger.getEffectiveLevel() > ProcessWrapper.loglevel:
            self.enable_print()

        # close sfd so we notice when the child is gone
        os.close(sfd)
        # get a file object from the fd
        buf = b""
        while True:
            try:
                raw = os.read(mfd, 4096)
            except BlockingIOError as ex:
                # wait for new data and retry
                select.select([mfd], [], [mfd], 0.1)
                continue
            except OSError as e:
                if e.errno == 5:
                    break
                raise

            if raw:
                buf += raw
                *parts, buf = buf.split(b'\r')
                res.extend(parts)
                for part in parts:
                    for callback in self.callbacks:
                        callback(part, process)
            process.poll()
            if process.returncode is not None:
                break

        os.close(mfd)
        process.wait()
        if buf:
            # process incomplete line
            res.append(buf)
            if buf[-1] != b'\n':
                buf += b'\n'
            for callback in self.callbacks:
                callback(buf, process)

        if print_on_silent_log and logger.getEffectiveLevel() > ProcessWrapper.loglevel:
            self.disable_print()

        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode,
                                                command,
                                                output=b'\r'.join(res))
        # this converts '\r\n' to '\n' to be more compatible to the behaviour
        # of the normal subprocess module
        return b'\n'.join([r.strip(b'\n') for r in res])

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
