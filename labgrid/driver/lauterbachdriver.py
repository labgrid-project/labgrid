import logging
import os
import re
import subprocess
import time
from importlib import import_module

import attr

from ..factory import target_factory
from ..protocol import BootstrapProtocol
from ..resource.lauterbach import (NetworkLauterbachDebugger,
                                   RemoteUSBLauterbachDebugger)
from ..resource.udev import USBLauterbachDebugger
from ..step import step
from ..util.agentwrapper import AgentWrapper
from ..util.helper import get_free_port, get_uname_machine, processwrapper
from ..util.managedfile import ManagedFile
from ..util.proxy import proxymanager
from .common import Driver
from .exception import ExecutionError


@target_factory.reg_driver
@attr.s(eq=False)
class LauterbachDriver(Driver, BootstrapProtocol):
    """
    Allows to use a Lauterbach TRACE32 USB or Ethernet debugger.
    Both creation of interactive debug sessions and
    automation via Remote API are supported.

    Args:
        t32_sys (str): optional, base folder of the TRACE32 installation
        t32_bin (str, default="t32marm"): name of the TRACE32 architecture executable `t32m*`
        script (str): optional, path to the `.cmm` script to run on startup of TRACE32
        script_args_bootstrap  (str, list): parameters passed to `.cmm` script with labgrid command `bootstrap`
        script_args_debug (str, list): parameters passed to `.cmm` script for the methods `start()` and `control()`
        enable_rcl (bool, default=True): enables the Remote API interface for automation tasks
    """
    bindings = {
        "interface": {
            "USBLauterbachDebugger",
            "RemoteUSBLauterbachDebugger",
            "NetworkLauterbachDebugger"
        },
    }
    t32_bin = attr.ib(default="t32marm", validator=attr.validators.instance_of(str))
    t32_sys = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str))
    )
    script = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str))
    )
    script_args_debug = attr.ib(
        default=attr.Factory(list),
        validator=attr.validators.optional(attr.validators.instance_of((str, list)))
    )
    script_args_bootstrap = attr.ib(
        default=attr.Factory(list),
        validator=attr.validators.optional(attr.validators.instance_of((str, list)))
    )
    enable_rcl = attr.ib(
        default=True,
        validator=attr.validators.optional(attr.validators.instance_of(bool))
    )

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.logger = logging.getLogger(f"{self}:{self.target}")
        self._pystart = import_module("lauterbach.trace32.pystart")
        self._pyrcl = import_module("lauterbach.trace32.rcl")

        self._pathmap = {
            "aarch64": "bin/linux-aarch64",
            "amd64": "bin/pc_linux64",
            "armhf": "bin/linux-armhf"
        }

        self.t32_sys = self._get_install_dir(self.t32_sys)
        self.logger.info("using `t32_sys`: %s", self.t32_sys)

        self.t32_bin = self._get_t32_bin(self.t32_bin)
        self.logger.info("using `t32_bin`: %s", self.t32_bin)

        self.script = self._get_script(self.script)
        self.logger.info("using `script`: %s", self.script)

        self.connection = None
        self.t32tcpusb = None
        self.powerview = None
        self.rcl_port = None

    def _get_install_dir(self, path):
        """
        Detects TRACE32 installation folder via environment, `T32SYS`
        environment variable or a set of default paths.
        """
        assert self.target
        lookup = []
        if path:
            # We support absolute paths or relative paths either to the user's home
            # directory or the current working directory. Otherwise, the path must
            # map to a path key in the environment configuration.
            if re.match(r"^(~|\.\.?/|/)", os.path.expandvars(path)):
                lookup.append(path)
            else:
                if not self.target.env:
                    raise ExecutionError(
                        "Provide either an absolute path, a relative path from home folder or "
                        "working directory, or an environment for `t32_sys`."
                    )
                lookup.append(self.target.env.config.get_path(path))
        else:
            lookup += [
                os.environ.get("T32SYS", None),
                "~/t32",
                "/opt/t32"
            ]

        lookup = filter(lambda x: x, lookup)
        if self.target.env:
            lookup = map(self.target.env.config.resolve_path, lookup)
        else:
            lookup = map(os.path.expanduser, map(os.path.expandvars, lookup))

        paths = list(filter(os.path.exists, lookup))
        if not paths:
            raise ExecutionError("TRACE32 installation folder not found.")

        self.logger.info(
            "Found TRACE32 installation paths %s%s.",
            ", ".join(paths[:-1]), (", and " + paths[-1]) if len(paths) > 1 else ""
        )
        return paths[0]

    def _get_t32_bin(self, path):
        """Selects the PowerView executable."""
        if not path:
            return None

        assert self.target
        # The PowerView executable can be either a path or an executable name.
        # We support absolute paths or relative paths either to the user's home
        # directory or the current working directory. Otherwise, the path must
        # map to a path key in the environment configuration.
        # If we cannot identify the value as path or configuration key, then we
        # assume that it must be an executable name.
        ispath = re.match(r"^(~|\.\.?/|/)", os.path.expandvars(path))
        if ispath:
            if self.target.env:
                return self.target.env.config.resolve_path(path)
            else:
                return os.path.expanduser(os.path.expandvars(path))
        elif path.startswith("t32m"):
            return path
        elif not self.target.env:
            raise ExecutionError(
                "Provide either an absolute path, a relative path from home folder or "
                "working directory, an executable name, or an environment for `t32_bin`."
            )

        try:
            bin_ = self.target.env.config.get_path(path)
        except KeyError:
            return path

        return self.target.env.config.resolve_path(bin_)

    def _get_script(self, path):
        """Resolves path to the given TRACE32 script file."""
        if not path:
            return None

        assert self.target
        # We support absolute paths or relative paths either to the user's home
        # directory or the current working directory. Otherwise, the path must
        # map to a path key in the environment configuration.
        ispath = re.match(r"^(~|\.\.?/|/)", os.path.expandvars(path))
        if ispath:
            if self.target.env:
                return self.target.env.config.resolve_path(path)
            else:
                return os.path.expanduser(os.path.expandvars(path))
        elif not self.target.env:
            raise ExecutionError(
                "Provide either an absolute path, a relative path from home folder or "
                "working directory, or an environment for `script`."
            )

        try:
            script = self.target.env.config.get_path(path)
        except KeyError:
            return path

        return self.target.env.config.resolve_path(script)

    def _get_host_t32tcpusb_version(self):
        """Find matching TRACE32 `t32tcpusb` version for the client's host architecture."""
        assert self.t32_sys

        arch = get_uname_machine()
        bin_ = self._pathmap.get(arch)
        if not bin_:
            raise ExecutionError(f"No `t32tcpusb` variant for architecture `{arch}` of the host machine.")

        t32tcpusb = os.path.join(self.t32_sys, bin_, "t32tcpusb")

        self.logger.debug("Using host `t32tcpusb %s", t32tcpusb)
        if not os.path.exists(t32tcpusb):
            raise ExecutionError(f"Cannot locate `t32tcpusb` for host architecture `{arch}`: Path `{bin_}` is missing")

        # Converts string `Sw.Version: N.<year>.<month>.<revision>` to
        # hex number `0x<year><month>`
        version = 0x0
        output = processwrapper.check_output([t32tcpusb, "-h"]).decode("utf-8")
        versionmatch = re.search(r"Version:\s[NSRP]\.(\d{4})\.(\d{2})\.\d+", str(output))

        if versionmatch is not None:
            version = int(f"0x{versionmatch[1]}{versionmatch[2]}", 16)

        return version

    def _deploy_remote_t32tcpusb(self):
        """Sends matching `t32tcpusb` variant to the remote machine and starts it there."""
        assert self.t32_sys

        agent = AgentWrapper(self.interface.host)
        hosttools = agent.load("hosttools")

        arch = hosttools.get_uname_machine()
        self.logger.debug("Remote architecture is `%s`", arch)

        bin_ = self._pathmap.get(arch)
        if not bin_:
            raise ExecutionError(f"No `t32tcpusb` variant for architecture `{arch}` of the remote machine.")

        t32tcpusb = os.path.join(self.t32_sys, bin_, "t32tcpusb")
        self.logger.debug("Using remote t32tcpusb: %s", t32tcpusb)
        if not os.path.exists(t32tcpusb):
            raise ExecutionError(
                f"Cannot locate `t32tcpusb` for remote architecture `{arch}`: Path `{bin_}` is missing."
            )

        mf = ManagedFile(t32tcpusb, self.interface)
        mf.sync_to_resource()

        port = agent.get_free_port()
        cmd = self.interface.command_prefix
        # Force a tty to get `terminate` working
        cmd.insert(-2, "-tt")
        cmd += [
            mf.get_remote_path(),
            "--device",
            f"{self.interface.busnum:03d}:{self.interface.devnum:03d}",
            str(port)
        ]

        self.logger.debug("Running command `%s`", " ".join(cmd))
        return subprocess.Popen(cmd, stdout=subprocess.PIPE), port

    def on_activate(self):
        assert hasattr(self, 'interface')

        if isinstance(self.interface, USBLauterbachDebugger):
            version = self._get_host_t32tcpusb_version()
            if version < 0x20_2004:
                raise ExecutionError(f"TRACE32 version {version:06x} is too old for supporting USB connections.")
            self.connection = self._pystart.USBConnection(device_path=f"/dev/bus/usb/{self.interface.busnum:03d}/{self.interface.devnum:03d}")

        elif isinstance(self.interface, NetworkLauterbachDebugger):
            if self.interface.protocol.lower() == "udp":
                # The proxy manager will switch to a "localhost" tunnel, if the
                # resources are only accessible via the SSH proxy mechanism.
                host, port = proxymanager.get_host_and_port(self.interface, default_port=9187)
                if host == "localhost":
                    raise ExecutionError("Proxy support is only available for PowerDebug X50/X51 devices")

                self.connection = self._pystart.UDPConnection(host)
            else:
                host, port = proxymanager.get_host_and_port(self.interface, default_port=9187)
                self.connection = self._pystart.TCPConnection(host, port)

        elif isinstance(self.interface, RemoteUSBLauterbachDebugger):
            version = self._get_host_t32tcpusb_version()
            if version < 0x20_2212:
                raise ExecutionError(f"`t32tcpusb` version {version:06x} is too old.")

            self.t32tcpusb, remote_port = self._deploy_remote_t32tcpusb()

            host, port = proxymanager.get_host_and_port(self.interface, default_port=remote_port)
            self.connection = self._pystart.USBProxyConnection(host, port)

        self.powerview = self._pystart.PowerView(self.connection, system_path=self.t32_sys)
        if self.enable_rcl:
            self.logger.info("Enabling Remote API interface")

        return super().on_activate()

    def on_deactivate(self):
        assert self.powerview
        if self.powerview.get_pid():
            self.powerview.stop()

        if self.t32tcpusb:
            self.logger.debug("Terminating `t32tcpusb` on exporter")
            self.t32tcpusb.terminate()

        self.connection = None

        return super().on_deactivate()

    def _configure_powerview(self, cmd_parameters, user_parameters):
        assert self.powerview and self.t32_bin
        if self.t32_bin.startswith("t32m"):
            self.powerview.target = self.t32_bin
        else:
            self.powerview.force_executable = self.t32_bin

        startup_parameters = []
        startup_parameters += cmd_parameters
        if isinstance(user_parameters, list):
            startup_parameters += user_parameters
        elif startup_parameters:
            startup_parameters += [user_parameters]

        if self.script:
            self.powerview.startup_script = self.script
            self.powerview.startup_parameter = startup_parameters

    def _configure_bootstrap_mode(self, file):
        cmd = ["LABGRID_COMMAND=BOOTSTRAP", f"FILE={file}"]

        self._configure_powerview(cmd, self.script_args_bootstrap)

    def _configure_debug_mode(self):
        cmd = ["LABGRID_COMMAND=DEBUGGER"]

        self._configure_powerview(cmd, self.script_args_debug)
        if self.enable_rcl:
            assert self.powerview
            self.rcl_port = get_free_port()
            self.powerview.add_interface(self._pystart.RCLInterface(
                port=self.rcl_port,
                protocol="TCP"
            ))

    def _start_powerview_debug_mode(self):
        self._configure_debug_mode()

        assert self.powerview
        self.logger.debug(self.powerview.get_configuration_string())
        self.powerview.start()

    def _connect(self):
        if not self.enable_rcl:
            raise ExecutionError(
                "Remote API interface has been disabled. "
                "Use the parameter `enable_rcl` to enable it."
            )

        assert self._pyrcl and self.rcl_port
        return self._pyrcl.connect(port=self.rcl_port, protocol="TCP")

    @Driver.check_active
    def start(self):
        """Opens the TRACE32 debug frontend for interactive debugging."""

        self._start_powerview_debug_mode()
        assert self.powerview
        self.powerview.wait()

    @Driver.check_active
    def control(self):
        """
        Takes control of the TRACE32 debug frontend, so that it can receive automation commands.
        Returns a `pyrcl` instance for controlling the debugger via its Remote API interface.
        """
        assert self.powerview
        if not self.powerview.get_pid():
            self._start_powerview_debug_mode()

        return self._connect()

    @Driver.check_active
    @step(args=['commands'])
    def execute(self, commands: list):
        """
        Executes a set of commands. Starts TRACE32 debug frontend if not already running.

        Args:
            commands (list): commands to execute
        """
        assert self.powerview
        if not self.powerview.get_pid():
            self._start_powerview_debug_mode()

        with self._connect() as rcl:
            for cmd in commands:
                rcl.cmd(cmd)
                # Poll for command completion
                while self.powerview.get_pid() and rcl._get_practice_state():
                    time.sleep(0.07)

    # Bootstrap protocol
    @Driver.check_active
    @step(args=['filename'])
    def load(self, filename=None):
        """
        Bootstrap a bootloader onto a board.

        Args:
            filename (str, default=None): filename of image to write
        """
        if not self.script:
            raise ExecutionError("Cannot bootstrap without `script` parameter")

        if not filename and self.image:
            filename = self.target.env.config.get_image_path(self.image)

        self._configure_bootstrap_mode(filename)

        assert self.powerview
        self.powerview.screen = False
        self.logger.debug(self.powerview.get_configuration_string())
        self.powerview.start()
        self.powerview.wait()
