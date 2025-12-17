import contextlib
import shutil
import subprocess
import warnings

import attr

from ..factory import target_factory
from ..resource import NetworkCANPort, RawCANPort
from ..resource.udev import USBCANPort
from ..util.helper import processwrapper
from ..util.proxy import proxymanager
from .common import Driver


@target_factory.reg_driver
@attr.s(eq=False)
class CANDriver(Driver):
    bindings = {
        "port": {"NetworkCANPort", "RawCANPort", "USBCANPort"},
    }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.ifname = None
        self.child = None
        self.can_helper = shutil.which("labgrid-can-interface")
        if self.can_helper is None:
            self.can_helper = "/usr/sbin/labgrid-can-interface"
            warnings.warn(f"labgrid-can-interface helper not found, falling back to {self.can_helper}")
        self.helper_wrapper = ["sudo", self.can_helper]
        self.cannelloni_bin = shutil.which("cannelloni")
        if self.cannelloni_bin is None:
            self.cannelloni_bin = "/usr/bin/cannelloni"
            warnings.warn(f"cannelloni binary not found, falling back to {self.cannelloni_bin}")

    def _wrap_command(self, cmd):
        return self.helper_wrapper + cmd

    def on_activate(self):
        if isinstance(self.port, NetworkCANPort):
            host, port = proxymanager.get_host_and_port(self.port)
            # XXX The port might not be unique, use something better
            self.ifname = f"lg_vcan{port}"

            cmd_ip_add = self._wrap_command(["ip", self.ifname, "add"])
            processwrapper.check_output(cmd_ip_add)

            cmd_ip_up = self._wrap_command(["ip", self.ifname, "up"])
            processwrapper.check_output(cmd_ip_up)

            cmd_tc = self._wrap_command(["tc", self.ifname, "set-bitrate", str(self.port.speed)])
            processwrapper.check_output(cmd_tc)
            cmd_cannelloni = [
                self.cannelloni_bin,
                "-C", "c",
                "-I", f"{self.ifname}",
                "-R", f"{host}",
                "-r", f"{port}",
                ]
            self.logger.info("Running command: %s", cmd_cannelloni)
            self.child = subprocess.Popen(cmd_cannelloni)
            # XXX How to check the process? Ideally read output and find the "connected" string?
        elif isinstance(self.port, (RawCANPort, USBCANPort)):
            host = None
            self.ifname = self.port.ifname

            cmd_down = self._wrap_command(["ip", self.ifname, "down"])
            processwrapper.check_output(cmd_down)

            cmd_type_bitrate = self._wrap_command(["ip", self.ifname, "set-bitrate", str(self.port.speed)])
            processwrapper.check_output(cmd_type_bitrate)

            cmd_up = self._wrap_command(["ip", self.ifname, "up"])
            processwrapper.check_output(cmd_up)
        else:
            raise NotImplementedError(f"Unsupported CAN resource: {self.port}")

    def on_deactivate(self):
        ifname = self.ifname
        self.ifname = None
        if isinstance(self.port, NetworkCANPort):
            assert self.child
            child = self.child
            self.child = None
            child.terminate()
            try:
                child.wait(2.0)
            except subprocess.TimeoutExpired:
                self.logger.warning("cannelloni on %s still running after SIGTERM", ifname)
                child.kill()
                child.wait(1.0)
            self.logger.info("stopped cannelloni for interface %s", ifname)

            cmd_ip_del = self._wrap_command(["ip", ifname, "del"])
            processwrapper.check_output(cmd_ip_del)
        else:
            cmd_down = self._wrap_command(["ip", ifname, "down"])
            processwrapper.check_output(cmd_down)

    @Driver.check_bound
    def get_export_vars(self):
        export_vars = {
            "ifname": self.ifname,
            "speed": str(self.port.speed),
        }
        if isinstance(self.port, NetworkCANPort):
            host, port = proxymanager.get_host_and_port(self.port)
            export_vars["host"] = host
            export_vars["port"] = str(port)
        return export_vars
