"""The QEMUDriver implements a driver to use a QEMU target"""
import atexit
import select
import shlex
import shutil
import socket
import subprocess
import re
import tempfile
import time

import attr
from pexpect import TIMEOUT

from ..factory import target_factory
from ..protocol import PowerProtocol, ConsoleProtocol
from ..step import step
from .common import Driver
from .consoleexpectmixin import ConsoleExpectMixin
from ..util.qmp import QMPMonitor, QMPError
from .exception import ExecutionError


@target_factory.reg_driver
@attr.s(eq=False)
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
        extra_args (str): optional, extra QEMU arguments passed directly to the QEMU binary
        boot_args (str): optional, additional kernel boot argument
        kernel (str): optional, reference to the images key for the kernel
        disk (str): optional, reference to the images key for the disk image
        disk_opts (str): optional, additional QEMU disk options
        flash (str): optional, reference to the images key for the flash image
        rootfs (str): optional, reference to the paths key for use as the virtio-9p filesystem
        dtb (str): optional, reference to the image key for the device tree
        bios (str): optional, reference to the image key for the bios image
        display (str, default="none"): optional, display output to enable; must be one of:
            none: Do not create a display device
            fb-headless: Create a headless framebuffer device
            egl-headless: Create a headless GPU-backed graphics card. Requires host support
            qemu-default: Don't override QEMU default settings
        nic (str): optional, configuration string to pass to QEMU to create a network interface
    """
    qemu_bin = attr.ib(validator=attr.validators.instance_of(str))
    machine = attr.ib(validator=attr.validators.instance_of(str))
    cpu = attr.ib(validator=attr.validators.instance_of(str))
    memory = attr.ib(validator=attr.validators.instance_of(str))
    extra_args = attr.ib(
        default='',
        validator=attr.validators.optional(attr.validators.instance_of(str)))
    boot_args = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str)))
    kernel = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str)))
    disk = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str)))
    disk_opts = attr.ib(
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
    bios = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str)))
    display = attr.ib(
        default="none",
        validator=attr.validators.optional(attr.validators.and_(
            attr.validators.instance_of(str),
            attr.validators.in_(
                ["none", "fb-headless", "egl-headless", "qemu-default"]
            ),
        ))
    )
    nic = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str)))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.status = 0
        self.txdelay = None
        self._child = None
        self._tempdir = None
        self._socket = None
        self._clientsocket = None
        self._forwarded_ports = {}
        atexit.register(self._atexit)

    def _atexit(self):
        if not self._child:
            return
        self._child.terminate()
        try:
            self._child.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            self._child.kill()
            self._child.communicate(timeout=1)

    def get_qemu_version(self, qemu_bin):
        p = subprocess.run([qemu_bin, "-version"], stdout=subprocess.PIPE, encoding="utf-8")
        if p.returncode != 0:
            raise ExecutionError(f"Unable to get QEMU version. QEMU exited with: {p.returncode}")

        m = re.search(r'(?P<major>\d+)\.(?P<minor>\d+)\.(?P<micro>\d+)', p.stdout.splitlines()[0])
        if m is None:
            raise ExecutionError(f"Unable to find QEMU version in: {p.stdout.splitlines()[0]}")

        return (int(m.group('major')), int(m.group('minor')), int(m.group('micro')))

    def get_qemu_base_args(self):
        """Returns the base command line used for Qemu without the options
        related to QMP. These options can be used to start an interactive
        Qemu manually for debugging tests
        """
        cmd = []

        qemu_bin = self.target.env.config.get_tool(self.qemu_bin)
        if qemu_bin is None:
            raise KeyError(
                "QEMU Binary Path not configured in tools configuration key")
        cmd = [qemu_bin]

        qemu_version = self.get_qemu_version(qemu_bin)

        boot_args = []

        if self.kernel is not None:
            cmd.append("-kernel")
            cmd.append(
                self.target.env.config.get_image_path(self.kernel))
        if self.disk is not None:
            disk_path = self.target.env.config.get_image_path(self.disk)
            disk_format = "raw"
            if disk_path.endswith(".qcow2"):
                disk_format = "qcow2"
            disk_opts = ""
            if self.disk_opts:
                disk_opts = f",{self.disk_opts}"
            if self.machine == "vexpress-a9":
                cmd.append("-drive")
                cmd.append(
                    f"if=sd,format={disk_format},file={disk_path},id=mmc0{disk_opts}")
                boot_args.append("root=/dev/mmcblk0p1 rootfstype=ext4 rootwait")
            elif self.machine in ["pc", "q35", "virt"]:
                cmd.append("-drive")
                cmd.append(
                    f"if=virtio,format={disk_format},file={disk_path}{disk_opts}")
                boot_args.append("root=/dev/vda rootwait")
            else:
                raise NotImplementedError(
                    f"QEMU disk image support not implemented for machine '{self.machine}'"
                )
        if self.rootfs is not None:
            cmd.append("-fsdev")
            cmd.append(
                f"local,id=rootfs,security_model=none,path={self.target.env.config.get_path(self.rootfs)}")  # pylint: disable=line-too-long
            cmd.append("-device")
            cmd.append(
                "virtio-9p-device,fsdev=rootfs,mount_tag=/dev/root")
            boot_args.append("root=/dev/root rootfstype=9p rootflags=trans=virtio")
        if self.dtb is not None:
            cmd.append("-dtb")
            cmd.append(self.target.env.config.get_image_path(self.dtb))
        if self.flash is not None:
            cmd.append("-drive")
            cmd.append(
                f"if=pflash,format=raw,file={self.target.env.config.get_image_path(self.flash)},id=nor0")  # pylint: disable=line-too-long
        if self.bios is not None:
            cmd.append("-bios")
            cmd.append(
                self.target.env.config.get_image_path(self.bios))

        if "-append" in shlex.split(self.extra_args):
            raise ExecutionError("-append in extra_args not allowed, use boot_args instead")

        cmd.extend(shlex.split(self.extra_args))
        cmd.append("-machine")
        cmd.append(self.machine)
        cmd.append("-cpu")
        cmd.append(self.cpu)
        cmd.append("-m")
        cmd.append(self.memory)
        if self.display == "none":
            cmd.append("-nographic")
        elif self.display == "fb-headless":
            cmd.append("-display")
            cmd.append("none")
        elif self.display == "egl-headless":
            if qemu_version >= (6, 1, 0):
                cmd.append("-device")
                cmd.append("virtio-vga-gl")
            else:
                cmd.append("-vga")
                cmd.append("virtio")
            cmd.append("-display")
            cmd.append("egl-headless")
        elif self.display != "qemu-default":
            raise ExecutionError(f"Unknown display '{self.display}'")

        if self.nic:
            cmd.append("-nic")
            cmd.append(self.nic)

        if self.boot_args is not None:
            boot_args.append(self.boot_args)
        if self.kernel is not None and boot_args:
            cmd.append("-append")
            cmd.append(" ".join(boot_args))

        return cmd

    def on_activate(self):
        self._tempdir = tempfile.mkdtemp(prefix="labgrid-qemu-tmp-")
        sockpath = f"{self._tempdir}/serialrw"
        self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._socket.bind(sockpath)
        self._socket.listen(0)

        self._cmd = self.get_qemu_base_args()

        self._cmd.append("-S")
        self._cmd.append("-qmp")
        self._cmd.append("stdio")

        self._cmd.append("-chardev")
        self._cmd.append(f"socket,id=serialsocket,path={sockpath}")
        self._cmd.append("-serial")
        self._cmd.append("chardev:serialsocket")

    def on_deactivate(self):
        if self.status:
            self.off()
        if self._clientsocket:
            self._clientsocket.close()
            self._clientsocket = None
        self._socket.close()
        self._socket = None
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

        try:
            self.qmp = QMPMonitor(self._child.stdout, self._child.stdin)
        except QMPError as exc:
            if self._child.poll() is not None:
                _, err = self._child.communicate()
                raise IOError(
                    f"QEMU error: {err} (exitcode={self._child.returncode})"
                ) from exc
            raise

        self.status = 1

        # Restore port forwards
        for v in self._forwarded_ports.values():
            self._add_port_forward(*v)

        self.monitor_command("cont")

    @step()
    def off(self):
        """Stop the emulator using a monitor command and await the exitcode"""
        if not self.status:
            return
        self.monitor_command('quit')
        if self._child.wait() != 0:
            self._child.communicate()
            raise IOError
        self._child = None
        self.status = 0

    def cycle(self):
        """Cycle the emulator by restarting it"""
        self.off()
        self.on()

    @step(result=True, args=['command', 'arguments'])
    def monitor_command(self, command, arguments={}):
        """Execute a monitor_command via the QMP"""
        if not self.status:
            raise ExecutionError(
                "Can't use monitor command on non-running target")
        return self.qmp.execute(command, arguments)

    def _add_port_forward(self, proto, local_address, local_port, remote_address, remote_port):
        self.monitor_command(
            "human-monitor-command",
            {"command-line": f"hostfwd_add {proto}:{local_address}:{local_port}-{remote_address}:{remote_port}"},
        )

    def add_port_forward(self, proto, local_address, local_port, remote_address, remote_port):
        self._add_port_forward(proto, local_address, local_port, remote_address, remote_port)
        self._forwarded_ports[(proto, local_address, local_port)] = (proto, local_address, local_port, remote_address, remote_port)

    def remove_port_forward(self, proto, local_address, local_port):
        del self._forwarded_ports[(proto, local_address, local_port)]
        self.monitor_command(
            "human-monitor-command",
            {"command-line": f"hostfwd_remove {proto}:{local_address}:{local_port}"},
        )

    def _read(self, size=1, timeout=10, max_size=None):
        ready, _, _ = select.select([self._clientsocket], [], [], timeout)
        if ready:
            # Collect some more data
            time.sleep(0.01)
            # Always read a page, regardless of size
            size = 4096
            size = min(max_size, size) if max_size else size
            res = self._clientsocket.recv(size)
        else:
            raise TIMEOUT(f"Timeout of {timeout:.2f} seconds exceeded")
        return res

    def _write(self, data):
        return self._clientsocket.send(data)

    def __str__(self):
        return f"QemuDriver({self.target.name})"
