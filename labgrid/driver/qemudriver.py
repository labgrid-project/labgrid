"""The QEMUDriver implements a driver to use a QEMU target"""
import logging
import select
import shlex
import shutil
import socket
import subprocess
import tempfile

import attr
from pexpect import TIMEOUT

from ..factory import target_factory
from ..protocol import PowerProtocol, ConsoleProtocol
from ..step import step
from .common import Driver
from .consoleexpectmixin import ConsoleExpectMixin
from ..util.qmp import QMPMonitor
from .exception import ExecutionError


@target_factory.reg_driver
@attr.s
class QEMUDriver(ConsoleExpectMixin, Driver, PowerProtocol, ConsoleProtocol):
    """
    The QEMUDriver implements an interface to start targets as qemu instances.

    Args:
        qemu_bin (str): Path to the QEMU binary
        machine (str): QEMU machine type
        cpu (str): QEMU cpu type
        memory (str): QEMU memory size (ends with M or G)
        boot_args (str): kernel boot argument
        extra_args (str): extra QEMU arguments, are passed directly to the QEMU binary
        kernel (str): path to the kernel image
        rootfs (str): path to the rootfs for the virtio-9p filesystem
        dtb (str): optional, path to the compiled device tree
    """
    qemu_bin = attr.ib(validator=attr.validators.instance_of(str))
    machine = attr.ib(validator=attr.validators.instance_of(str))
    cpu = attr.ib(validator=attr.validators.instance_of(str))
    memory = attr.ib(validator=attr.validators.instance_of(str))
    boot_args = attr.ib(validator=attr.validators.instance_of(str))
    extra_args = attr.ib(validator=attr.validators.instance_of(str))
    kernel = attr.ib(
        validator=attr.validators.optional(attr.validators.instance_of(str)))
    rootfs = attr.ib(
        validator=attr.validators.optional(attr.validators.instance_of(str)))
    dtb = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str)))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.logger = logging.getLogger("{}:".format(self))
        self.status = 0
        self.txdelay = None
        self._child = None
        self._tempdir = None
        self._socket = None
        self._clientsocket = None

    def on_activate(self):
        self._tempdir = tempfile.mkdtemp(prefix="labgrid-qemu-tmp-")
        sockpath = "{}/serialrw".format(self._tempdir)
        self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._socket.bind(sockpath)
        self._socket.listen(0)

        self._cmd = [self.qemu_bin]

        if self.kernel:
            self._cmd.append("-kernel")
            self._cmd.append(self.kernel)
        if self.rootfs:
            self._cmd.append("-fsdev")
            self._cmd.append(
                "local,id=rootfs,security_model=none,path={}".format(
                    self.rootfs))
            self._cmd.append("-device")
            self._cmd.append(
                "virtio-9p-device,fsdev=rootfs,mount_tag=/dev/root")
        if self.dtb:
            self._cmd.append("-dtb")
            self._cmd.append(self.dtb)

        self._cmd.extend(shlex.split(self.extra_args))
        self._cmd.append("-S")
        self._cmd.append("-qmp")
        self._cmd.append("stdio")
        self._cmd.append("-machine")
        self._cmd.append(self.machine)
        self._cmd.append("-cpu")
        self._cmd.append(self.cpu)
        self._cmd.append("-m")
        self._cmd.append(self.memory)
        self._cmd.append("-kernel")
        self._cmd.append(self.kernel)
        self._cmd.append("-nographic")
        self._cmd.append("-append")
        self._cmd.append(
            "root=/dev/root rootfstype=9p rootflags=trans=virtio {}".format(
                self.boot_args))
        self._cmd.append("-chardev")
        self._cmd.append("socket,id=serialsocket,path={}".format(sockpath))
        self._cmd.append("-serial")
        self._cmd.append("chardev:serialsocket")

    def on_deactivate(self):
        if self.status:
            self.off()
        shutil.rmtree(self._tempdir)

    @step()
    def on(self):
        """Start the QEMU subprocess, accept the unix socket connection and
        afterwards start the emulator using a QMP Command"""
        if self.status:
            return
        self.logger.debug("Starting with: %s", self._cmd)
        self._child = subprocess.Popen(
            self._cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE)

        # prepare for timeout handing
        self._clientsocket, address = self._socket.accept()
        self._clientsocket.setblocking(0)
        self.logger.debug("new connection from %s", address)
        self.qmp = QMPMonitor(self._child.stdout, self._child.stdin)
        self.status = 1
        self.monitor_command("cont")

    @step()
    def off(self):
        """Stop the emulator using a monitor command and await the exitcode"""
        if not self.status:
            return
        self.monitor_command('quit')
        if self._child.wait() != 0:
            raise IOError
        self.status = 0

    def cycle(self):
        """Cycle the emulator by restarting it"""
        self.off()
        self.on()

    @step(args=['command'])
    def monitor_command(self, command):
        """Execute a monitor_command via the QMP"""
        if not self.status:
            raise ExecutionError("Can't use monitor command on non-running target")
        self.qmp.execute(command)

    def _read(self, size=1, timeout=10):
        ready, _, _ = select.select([self._clientsocket], [], [], timeout)
        if ready:
            # Always read a page, regardless of size
            res = self._clientsocket.recv(4096)
            self.logger.debug(
                "Read %i bytes: %s, timeout %.2f, requested size %i",
                len(res), res, timeout, size)
        else:
            raise TIMEOUT("Timeout of %.2f seconds exceeded" % timeout)
        return res

    @step(args=['data'])
    def _write(self, data):
        self.logger.debug("Write %i bytes: %s", len(data), data)
        return self._clientsocket.send(data)
