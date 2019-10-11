import fcntl
import os
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

    @step(args=['command'], result=True, tag='process')
    def check_output(self, command):
        """Run a command and supply the output to callback functions"""
        res = []
        mfd, sfd = pty.openpty()
        flags = fcntl.fcntl(mfd, fcntl.F_GETFL)
        fcntl.fcntl(mfd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        process = subprocess.Popen(command, stderr=sfd,
                                   stdout=sfd, bufsize=0)
        # close sfd so we notice when the child is gone
        os.close(sfd)
        # get a file object from the fd
        omfd = os.fdopen(mfd, 'rb')
        buf = b""
        while True:
            try:
                raw = omfd.read(4096)
            except OSError as e:
                if e.errno == 5:
                    break
                raise
            if raw is None:
                # wait for new data and retry
                select.select([mfd], [], [mfd], 0.1)
                continue
            if raw:
                buf += raw
                *parts, buf = buf.split(b'\r\n')
                res.extend(parts)
                for part in parts:
                    for callback in self.callbacks:
                        callback(part)
            process.poll()
            if process.returncode is not None:
                break
        omfd.close()
        process.wait()
        if buf:
            # process incomplete line
            res.append(buf)
            for callback in self.callbacks:
                callback(buf)
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode,
                                                command,
                                                output=b'\n'.join(res))
        # this converts '\r\n' to '\n' to be more compatible to the behaviour
        # of the normal subprocess module
        return b'\n'.join(res)

    def register(self, callback):
        """Register a callback with the ProcessWrapper"""
        assert callback not in self.callbacks
        self.callbacks.append(callback)

    def unregister(self, callback):
        """Unregister a callback with the ProcessWrapper"""
        assert callback in self.callbacks
        self.callbacks.remove(callback)

    def enable_logging(self):
        """Enables process output to the logging interface.
        Loglevel is logging.INFO."""
        def log_callback(message):
            import logging
            logger = logging.getLogger("Process")
            logger.info(message.decode(encoding="utf-8", errors="replace"))
        self.register(log_callback)

    def enable_print(self):
        """Enables process output to print."""
        def print_callback(message):
            print(message.decode(encoding="utf-8", errors="replace"))
        self.register(print_callback)


processwrapper = ProcessWrapper()
