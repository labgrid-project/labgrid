import contextlib
import shutil
import subprocess

import attr

from ..factory import target_factory
from ..resource import CANPort, NetworkCANPort
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
        self.cannelloni_bin = shutil.which("cannelloni")
        if self.cannelloni_bin is None:
            self.cannelloni_bin = "/usr/bin/cannelloni"
            warnings.warn("cannelloni binary not found, falling back to %s", self.cannelloni_bin)

    def on_activate(self):
        if isinstance(self.port, NetworkCANPort):
            host, port = proxymanager.get_host_and_port(self.port)
            # XXX The port might not be unique, use something better
            self.ifname = f"lg_vcan{port}"
            # XXX How to handle permissions? sudo through helper like labgrid-raw-interface?
            cmd_ip_add = f"ip link add name {self.ifname} type vcan"
            processwrapper.check_output(cmd_ip_add.split())

            cmd_ip_up = f"ip link set dev {self.ifname} up"
            processwrapper.check_output(cmd_ip_up.split())

            # TODO Not all tc arguments are configurable
            cmd_tc = f"tc qdisc add dev {self.ifname} root tbf rate {self.port.speed}bit latency 100ms burst 1000"
            processwrapper.check_output(cmd_tc.split())
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
        else:
            host = None
            self.ifname = self.port.ifname

            cmd_down = f"ip link set {self.ifname} down"
            processwrapper.check_output(cmd_down.split())

            cmd_type_bitrate = f"ip link set {self.ifname} type can bitrate {self.port.speed}"
            processwrapper.check_output(cmd_type_bitrate.split())

            cmd_up = f"ip link set {self.ifname} up"
            processwrapper.check_output(cmd_up.split())

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
                log_subprocess_kernel_stack(self.logger, child)
                child.kill()
                child.wait(1.0)
            self.logger.info("stopped cannelloni for interface %s", ifname)

            cmd_ip_del = f"ip link del name {ifname}"
            processwrapper.check_output(cmd_ip_del.split())
        else:
            cmd_down = f"ip link set {ifname} down"
            processwrapper.check_output(cmd_down.split())

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
