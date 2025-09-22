import shlex
import subprocess

import attr

from ..factory import target_factory
from ..protocol import CommandProtocol, FileTransferProtocol, ResetProtocol
from ..resource.adb import ADBDevice, NetworkADBDevice, RemoteADBDevice
from ..step import step
from ..util.proxy import proxymanager
from .commandmixin import CommandMixin
from .common import Driver

# Default timeout for adb commands, in seconds
ADB_TIMEOUT = 10


@target_factory.reg_driver
@attr.s(eq=False)
class ADBDriver(CommandMixin, Driver, CommandProtocol, FileTransferProtocol, ResetProtocol):
    """ADB driver to execute commands, transfer files and reset devices via ADB."""

    bindings = {"device": {"ADBDevice", "NetworkADBDevice", "RemoteADBDevice"}}

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.target.env:
            self.tool = self.target.env.config.get_tool("adb")
        else:
            self.tool = "adb"

        if isinstance(self.device, ADBDevice):
            self._base_command = [self.tool, "-s", self.device.serialno]

        elif isinstance(self.device, NetworkADBDevice):
            self._host, self._port = proxymanager.get_host_and_port(self.device)
            self._base_command = [self.tool, "-H", self._host, "-P", str(self._port), "-s", self.device.serialno]

        elif isinstance(self.device, RemoteADBDevice):
            self._host, self._port = proxymanager.get_host_and_port(self.device)
            # ADB does not automatically remove a network device from its
            # devices list when the connection is broken by the remote, so the
            # adb connection may have gone "stale", resulting in adb blocking
            # indefinitely when making calls to the device. To avoid this,
            # always disconnect first.
            subprocess.run(
                [self.tool, "disconnect", f"{self._host}:{str(self._port)}"],
                stderr=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                timeout=ADB_TIMEOUT,
                check=False,
            )
            subprocess.run(
                [self.tool, "connect", f"{self._host}:{str(self._port)}"],
                stderr=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                timeout=ADB_TIMEOUT,
                check=True,
            )  # Connect adb client to TCP adb device
            self._base_command = [self.tool, "-s", f"{self._host}:{str(self._port)}"]

    def on_deactivate(self):
        if isinstance(self.device, RemoteADBDevice):
            # Clean up TCP adb device once the driver is deactivated
            subprocess.run(
                [self.tool, "disconnect", f"{self._host}:{str(self._port)}"],
                stderr=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                timeout=ADB_TIMEOUT,
                check=True,
            )

    # Command Protocol

    def _run(self, cmd, *, timeout=30.0, codec="utf-8", decodeerrors="strict"):
        cmd = [*self._base_command, "shell", *shlex.split(cmd)]
        result = subprocess.run(
            cmd,
            text=True,  # Automatically decode using default UTF-8
            capture_output=True,
            timeout=timeout,
        )
        return (
            result.stdout.splitlines(),
            result.stderr.splitlines(),
            result.returncode,
        )

    @Driver.check_active
    @step(args=["cmd"], result=True)
    def run(self, cmd, timeout=30.0, codec="utf-8", decodeerrors="strict"):
        return self._run(cmd, timeout=timeout, codec=codec, decodeerrors=decodeerrors)

    @step()
    def get_status(self):
        return 1

    # File Transfer Protocol

    @Driver.check_active
    @step(args=["filename", "remotepath", "timeout"])
    def put(self, filename: str, remotepath: str, timeout: float = ADB_TIMEOUT):
        subprocess.run(
            [*self._base_command, "push", filename, remotepath],
            timeout=timeout,
            check=True,
            stderr=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
        )

    @Driver.check_active
    @step(args=["filename", "destination", "timeout"])
    def get(self, filename: str, destination: str, timeout: float = ADB_TIMEOUT):
        subprocess.run(
            [*self._base_command, "pull", filename, destination],
            timeout=timeout,
            check=True,
            stderr=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
        )

    # Reset Protocol

    @Driver.check_active
    @step(args=["mode"])
    def reset(self, mode=None):
        valid_modes = ["bootloader", "recovery", "sideload", "sideload-auto-reboot"]
        cmd = [*self._base_command, "reboot"]

        if mode:
            if mode not in valid_modes:
                raise ValueError(f"{mode} must be one of: {', '.join(valid_modes)}")
            cmd.append(mode)

        subprocess.run(
            cmd,
            timeout=ADB_TIMEOUT,
            check=True,
            stderr=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
        )
