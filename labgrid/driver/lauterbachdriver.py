import logging
import os
import re
import subprocess

from importlib import import_module

import attr

from .exception import ExecutionError
from ..factory import target_factory
from ..protocol import BootstrapProtocol
from ..resource.lauterbach import NetworkLauterbachDebugger, RemoteUSBLauterbachDebugger
from ..resource.udev import USBLauterbachDebugger
from ..step import step
from ..util.agentwrapper import AgentWrapper
from ..util.helper import get_uname_machine, processwrapper
from ..util.managedfile import ManagedFile
from ..util.proxy import proxymanager

from .common import Driver


@target_factory.reg_driver
@attr.s(eq=False)
class LauterbachDriver(Driver, BootstrapProtocol):
    """
    Args:
        t32_sys (str): base folder of the TRACE32 installation (default ENV['T32SYS'] or ~/t32 or /opt/t32)
        t32_bin (str): name of the TRACE32 architecture executable `t32m*` (default `t32marm`)

        script  (str): path to the `.cmm` script to run on startup of TRACE32
                       first parameter is the used labgrid command e.g. `debugger, write-image`
        script_args_debug (str, list):
                       parameters passed to `.cmm` script with labgrid command `debugger`
        script_args_bootstrap  (str, list):
                        parameters passed to `.cmm` script with labgrid command `bootstrap`
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
        validator=attr.validators.optional(attr.validators.instance_of((str,list)))
        )
    script_args_bootstrap = attr.ib(
        default=attr.Factory(list),
        validator=attr.validators.optional(attr.validators.instance_of((str,list)))
        )

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.logger = logging.getLogger(f"{self}:{self.target}")
        self._pystart = import_module('lauterbach.trace32.pystart')

        self._pathmap = {
            "aarch64": "bin/linux-aarch64",
            "amd64":   "bin/pc_linux64",
            "armhf":   "bin/linux-armhf"
            }

        # detect TRACE32 installation folder via environment/T32SYS environment or default pathes
        t32sys = []
        if self.t32_sys:
            #  `t32_sys` may be absolute or a key in the path configuration
            if os.path.isabs(self.t32_sys):
                t32sys.append(self.t32_sys)
            else:
                t32sys.append(self.target.env.config.get_path(self.t32_sys))
        else:
            t32sys += [
                os.environ.get("T32SYS", None),
                "~/t32",
                "/opt/t32"
                ]
        # FIXME same as for openocd driver
        # make sure we always have an environment or config
        t32sys = filter(lambda x: x, t32sys)
        if self.target.env:
            t32sys = map(self.target.env.config.resolve_path, t32sys)
        t32sys = list(filter(os.path.exists, t32sys))
        if len(t32sys)==0:
            raise ExecutionError("TRACE32 installation folder not found")
        self.logger.info("Detected TRACE32 installation pathes [%s]", ", ".join(t32sys))
        self.t32sys=t32sys[0]
        self.logger.info("Using T32SYS: %s", self.t32sys)

        #  `script` may be absolute or a key in the path configuration
        if self.script:
            if not os.path.isabs(self.script):
                self.script = self.target.env.config.get_path(self.script)
            if self.target.env:
                self.script = self.target.env.config.resolve_path(self.script)
        
        self.connection = None
        self.t32tcpusb = None

    def _get_t32tcpusb_version(self):
        # get version running `t32tcpusb` on client
        t32tcpusb = os.path.join(self.t32sys, self._pathmap.get(get_uname_machine()), "t32tcpusb")
        self.logger.debug("Using host t32tcpusb: %s", t32tcpusb)
        if not os.path.exists(t32tcpusb):
            raise ExecutionError(f"Tool 't32tcpusb' for host architecture '{get_uname_machine()}' path '{self._pathmap.get(get_uname_machine())}' missing")

        version = 0x0
        # convert 'Sw.Version: N.<year>.<month>.<revision>' to 0x<year><month>
        output = processwrapper.check_output([t32tcpusb, '-h']).decode('utf-8')
        versionmatch = re.search(r"Version:\s[NSRP]\.(\d{4})\.(\d{2})\.\d+", str(output))

        if versionmatch is not None:
            version = int(f'0x{versionmatch[1]}{versionmatch[2]}', 16)

        return version

    def on_activate(self):
        if isinstance(self.interface, USBLauterbachDebugger):
            self.connection = self._pystart.USBConnection(f"{self.interface.busnum:03d}:{self.interface.devnum:03d}")
        elif isinstance(self.interface, NetworkLauterbachDebugger):
            if self.interface.protocol.lower() == "udp":
                host, port = proxymanager.get_host_and_port(self.interface, default_port=9187)
                if host != self.interface.host:
                    raise ExecutionError("Proxy support not available for legacy Lauterbach devices")
                self.connection = self._pystart.UDPConnection(self.interface.host)
            else:
                host, port = proxymanager.get_host_and_port(self.interface, default_port=9187)
                self.connection = self._pystart.TCPConnection(host, port)
        elif isinstance(self.interface, RemoteUSBLauterbachDebugger):
            version = self._get_t32tcpusb_version()
            if version<0x202212:
                raise ExecutionError(f"Version {version:06x} of `t32tcpusb` too old")

            agent = AgentWrapper(self.interface.host)
            hosttools = agent.load('hosttools')
            remoteArchitecture = hosttools.get_uname_machine()

            t32tcpusb = os.path.join(self.t32sys, self._pathmap.get(remoteArchitecture), "t32tcpusb")
            self.logger.debug("Using remote t32tcpusb: %s", t32tcpusb)
            if not os.path.exists(t32tcpusb):
                raise ExecutionError(f"Tool 't32tcpusb' for host architecture '{remoteArchitecture}' path '{self._pathmap.get(remoteArchitecture)}' missing")

            mf = ManagedFile(t32tcpusb, self.interface)
            mf.sync_to_resource()

            remotePort = agent.get_free_port()
            cmd = self.interface.command_prefix
            cmd.insert(-2, "-tt") # force a tty in order to get `terminate` working
            cmd += [
                mf.get_remote_path(),
                "--device",
                f"{self.interface.busnum:03d}:{self.interface.devnum:03d}",
                str(remotePort)
                ]

            self.logger.debug("Running command '%s'", " ".join(cmd))
            self.t32tcpusb = subprocess.Popen(cmd, stdout=subprocess.PIPE)

            host, port = proxymanager.get_host_and_port(self.interface, default_port=remotePort)
            self.connection = self._pystart.USBProxyConnection(host, port)
        return super().on_activate()

    def on_deactivate(self):
        if self.t32tcpusb:
            self.logger.debug("Try to terminate `t32tcpusb` on exporter")
            self.t32tcpusb.terminate()

        self.connection = None

        return super().on_deactivate()

    def _get_powerview_handle(self, command, script_args):
        pv = self._pystart.PowerView(self.connection, system_path=self.t32sys)

        if os.path.isabs(self.t32_bin):
            pv.force_executable = self.t32_bin
        else:
            pv.target = self.t32_bin

        if self.script:
            pv.startup_script = self.script
            pv.startup_parameter = [f"LABGRID_COMMAND={command.upper()}"]
            if isinstance(script_args, list):
                pv.startup_parameter += script_args
            elif len(script_args) > 0:
                pv.startup_parameter += [script_args]

        return pv

    # interactive debug
    @Driver.check_active
    def start(self):
        pv = self._get_powerview_handle("DEBUGGER", self.script_args_debug)

        self.logger.debug(pv.get_configuration_string())
        pv.start()
        pv.wait()

        return

    # Bootstrap protocol
    @Driver.check_active
    @step(args=['filename'])
    def load(self, filename=None):
        if self.script is None:
            raise ExecutionError("Mandatory TRACE32 configuration `script` is missing")

        if filename is None and self.image is not None:
            filename = self.target.env.config.get_image_path(self.image)
        mf = ManagedFile(filename, self.interface)
        mf.sync_to_resource()

        script_args = [f"FILE={filename}"]
        script_args += self.script_args_bootstrap

        pv = self._get_powerview_handle("BOOTSTRAP", script_args)
        pv.screen = False

        self.logger.debug(pv.get_configuration_string())
        pv.start()
        pv.wait()

        return
