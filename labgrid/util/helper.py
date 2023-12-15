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


def get_uname_machine():
    if hasattr(get_uname_machine, "architecture"):
        return get_uname_machine.architecture
    
    # translate `uname -m` output to debian/ubuntu architecture terms
    uname_translate = {
        "x86_64": "amd64"
    }
    # default: use ``uname -m``
    get_uname_machine.architecture = processwrapper.check_output(["uname","-m"]).decode("utf-8").rstrip()
    get_uname_machine.architecture = uname_translate.get(get_uname_machine.architecture, get_uname_machine.architecture)

    # check ELF header - inspired by /proc/sys/fs/binfmt_misc/qemu-*
    # Why? e.g. a AARCH64 Kernel can run a armhf userspace (buzzword: Raspian OS)
    binfmt = {
        "arm":     (b'\x7f\x45\x4c\x46\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00' # e_ident
                    b'\x02\x00\x28\x00'                                                 # e_type + e_machine
                    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' # e_<version,entry,phoff,shoff>
                    b'\x00\x00\x00\x00',                                                # e_flags
                    b'\xff\xff\xff\xff\xff\xff\xff\x00\xff\xff\xff\xff\xff\xff\xff\xff'
                    b'\xfe\xff\xff\xff'
                    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                    b'\x00\x00\x04\x00'),
        "armhf":   (b'\x7f\x45\x4c\x46\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                    b'\x02\x00\x28\x00'
                    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                    b'\x00\x00\x04\x00',
                    b'\xff\xff\xff\xff\xff\xff\xff\x00\xff\xff\xff\xff\xff\xff\xff\xff'
                    b'\xfe\xff\xff\xff'
                    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                    b'\x00\x00\x04\x00'),
        "aarch64": (b'\x7f\x45\x4c\x46\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                    b'\x02\x00\xb7\x00',
                    b'\xff\xff\xff\xff\xff\xff\xff\x00\xff\xff\xff\xff\xff\xff\xff\xff'
                    b'\xfe\xff\xff\xff'),
        "amd64":   (b'\x7f\x45\x4c\x46\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                    b'\x02\x00\x3e\x00',
                    b'\xff\xff\xff\xff\xff\xff\xff\x00\xff\xff\xff\xff\xff\xff\xff\xff'
                    b'\xfe\xff\xff\xff'),
    }

    elfheader = b''
    with open("/proc/self/exe", "rb") as exe:
        elfheader = exe.read(40)
    for arch, compare in binfmt.items():
        magic = compare[0]
        mask = compare[1]

        match = True
        for i in range(min(len(elfheader),len(magic),len(mask))):
            match = match and ((elfheader[i] & mask[i]) == magic[i])

        if match:
            get_uname_machine.architecture=arch
            break

    return get_uname_machine.architecture


@attr.s
class ProcessWrapper:
    callbacks = attr.ib(default=attr.Factory(list))
    loglevel = logging.INFO

    @step(args=['command'], result=True, tag='process')
    def check_output(self, command, *, print_on_silent_log=False, input=None, stdin=None): # pylint: disable=redefined-builtin
        """Run a command and supply the output to callback functions"""
        logger = logging.getLogger("Process")
        res = []
        mfd, sfd = pty.openpty()
        set_nonblocking(mfd)

        kwargs = {}

        stdin_r = None
        stdin_w = None
        if input is not None:
            stdin_r, stdin_w = os.pipe()
            kwargs['stdin'] = stdin_r
            set_nonblocking(stdin_w)
        elif stdin is not None:
            kwargs['stdin'] = stdin

        process = subprocess.Popen(command, stderr=sfd,
                                   stdout=sfd, bufsize=0, **kwargs)

        logger.log(ProcessWrapper.loglevel, "[%d] command: %s", process.pid, " ".join(command))

        # do not register/unregister already registered print_callback
        if ProcessWrapper.print_callback in self.callbacks:
            print_on_silent_log = False

        if print_on_silent_log and logger.getEffectiveLevel() > ProcessWrapper.loglevel:
            self.enable_print()

        if stdin_r is not None:
            os.close(stdin_r)

        # close sfd so we notice when the child is gone
        os.close(sfd)
        # get a file object from the fd
        buf = b""
        read_fds = [mfd]
        write_fds = []
        if stdin_w is not None:
            write_fds.append(stdin_w)

        while True:
            ready_r, ready_w, _ = select.select(read_fds, write_fds, [], 0.1)

            if mfd in ready_r:
                raw = None

                try:
                    raw = os.read(mfd, 4096)
                except BlockingIOError:
                    pass
                except OSError as e:
                    if e.errno == errno.EIO:
                        break
                    raise

                if raw:
                    buf += raw
                    *parts, buf = buf.split(b'\r')
                    res.extend(parts)
                    for part in parts:
                        for callback in self.callbacks:
                            callback(part, process)

            if stdin_w in ready_w:
                if input:
                    amt = 0
                    try:
                        amt = os.write(stdin_w, input)
                    except BlockingIOError:
                        pass
                    except OSError as e:
                        if e.errno == errno.EIO:
                            break
                        raise
                    input = input[amt:]

                if not input:
                    write_fds.remove(stdin_w)
                    os.close(stdin_w)
                    stdin_w = None

            process.poll()
            if process.returncode is not None:
                break

        if stdin_w is not None:
            os.close(stdin_w)

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
