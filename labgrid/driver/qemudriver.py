"""The QEMUDriver implements a driver to use a QEMU target"""
import atexit
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
@attr.s(cmp=False)
class QEMUDriver(ConsoleExpectMixin, Driver, PowerProtocol, ConsoleProtocol):
    """
    The QEMUDriver implements an interface to start targets as qemu instances.

    The kernel, flash, rootfs and dtb arguments refer to images and paths
    declared in the environment configuration.

    Args:
        qemu_bin (str): reference to the tools key for the QEMU binary
        machine (str): QEMU machine type
        cpu (str): QEMU cpu type
        memory (str): QEMU memory size (ends with M or G)
        extra_args (str): extra QEMU arguments, they are passed directly to the QEMU binary
        boot_args (str): optional, additional kernel boot argument
        kernel (str): optional, reference to the images key for the kernel
        disk (str): optional, reference to the images key for the disk image
        flash (str): optional, reference to the images key for the flash image
        rootfs (str): optional, reference to the paths key for use as the virtio-9p filesystem
        dtb (str): optional, reference to the image key for the device tree
    """
    qemu_bin = attr.ib(validator=attr.validators.instance_of(str))
    machine = attr.ib(validator=attr.validators.instance_of(str))
    cpu = attr.ib(validator=attr.validators.instance_of(str))
    memory = attr.ib(validator=attr.validators.instance_of(str))
    extra_args = attr.ib(validator=attr.validators.instance_of(str))
    boot_args = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str)))
    kernel = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str)))
    disk = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str)))
    rootfs = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str)))
    dtb = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str)))
    flash = attr.ib(
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
        atexit.register(self._atexit)

    def _atexit(self):
        if not self._child:
            return
        self._child.terminate()
        try:
            self._child.wait(1.0)
        except subprocess.TimeoutExpired:
            self._child.kill()
            self._child.wait(1.0)

    def on_activate(self):
        self._tempdir = tempfile.mkdtemp(prefix="labgrid-qemu-tmp-")
        sockpath = "{}/serialrw".format(self._tempdir)
        self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._socket.bind(sockpath)
        self._socket.listen(0)

        self.qemu_bin = self.target.env.config.get_tool(self.qemu_bin)
        if self.qemu_bin is None:
            raise KeyError(
                "QEMU Binary Path not configured in tools configuration key")
        self._cmd = [self.qemu_bin]

        boot_args = []

        if self.kernel is not None:
            self._cmd.append("-kernel")
            self._cmd.append(
                self.target.env.config.get_image_path(self.kernel))
        if self.disk is not None:
            disk_path = self.target.env.config.get_image_path(self.disk)
            if self.machine == "vexpress-a9":
                self._cmd.append("-drive")
                self._cmd.append(
                    "if=sd,format=raw,file={},id=mmc0".format(disk_path))
                boot_args.append("root=/dev/mmcblk0p1 rootfstype=ext4 rootwait")
            elif self.machine == "pc":
                self._cmd.append("-drive")
                self._cmd.append(
                    "if=virtio,format=raw,file={}".format(disk_path))
                boot_args.append("root=/dev/vda rootwait")
            else:
                raise NotImplementedError(
                    "QEMU disk image support not implemented for machine '{}'".format(self.machine)
                )
        if self.rootfs is not None:
            self._cmd.append("-fsdev")
            self._cmd.append(
                "local,id=rootfs,security_model=none,path={}".format(
                    self.target.env.config.get_path(self.rootfs)))
            self._cmd.append("-device")
            self._cmd.append(
                "virtio-9p-device,fsdev=rootfs,mount_tag=/dev/root")
            boot_args.append("root=/dev/root rootfstype=9p rootflags=trans=virtio")
        if self.dtb is not None:
            self._cmd.append("-dtb")
            self._cmd.append(self.target.env.config.get_image_path(self.dtb))
        if self.flash is not None:
            self._cmd.append("-drive")
            self._cmd.append(
                "if=pflash,format=raw,file={},id=nor0".format(
                    self.target.env.config.get_image_path(self.flash)))

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
        self._cmd.append("-nographic")
        self._cmd.append("-chardev")
        self._cmd.append("socket,id=serialsocket,path={}".format(sockpath))
        self._cmd.append("-serial")
        self._cmd.append("chardev:serialsocket")

        if self.boot_args is not None:
            boot_args.append(self.boot_args)
        if self.kernel is not None and boot_args:
            self._cmd.append("-append")
            self._cmd.append(" ".join(boot_args))

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
        self._child = None
        self.status = 0

    def cycle(self):
        """Cycle the emulator by restarting it"""
        self.off()
        self.on()

    @step(args=['command'])
    def monitor_command(self, command):
        """Execute a monitor_command via the QMP"""
        if not self.status:
            raise ExecutionError(
                "Can't use monitor command on non-running target")
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
