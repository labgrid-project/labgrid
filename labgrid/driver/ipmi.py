import subprocess

import attr

from ..factory import target_factory
from ..protocol import PowerProtocol
from ..step import step
from ..util.proxy import proxymanager
from .common import Driver
from .powerdriver import PowerResetMixin


@target_factory.reg_driver
@attr.s(eq=False)
class IMPIDriver(Driver, PowerResetMixin, PowerProtocol):
    """IMPIDriver - Driver to interface with a device via its IPMI interface.

    Currently supports:
     - Power Control
    """

    bindings = {"interface": {"IPMIInterface"}}

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.target.env:
            self.tool = self.target.env.config.get_tool("ipmitool")
        else:
            self.tool = "ipmitool"

        host, port = proxymanager.get_host_and_port(self.interface)

        self._base_command = [
            self.tool,
            "-I",
            self.interface.interface,
            "-H",
            host,
            "-p",
            str(port),
            "-U",
            self.interface.username,
            "-P",
            self.interface.password,
        ]

    @Driver.check_active
    @step()
    def on(self):
        subprocess.run([*self._base_command, "power", "on"], check=True, timeout=30)

    @Driver.check_active
    @step()
    def off(self):
        subprocess.run([*self._base_command, "power", "off"], check=True, timeout=30)

    @Driver.check_active
    @step()
    def cycle(self):
        subprocess.run([*self._base_command, "power", "cycle"], check=True, timeout=30)

    @Driver.check_active
    @step()
    def get(self):
        output = subprocess.run(
            [*self._base_command, "power", "status"], check=True, timeout=30, capture_output=True, text=True
        )
        if output.stdout == "Chassis Power is off\n":
            return False
        elif output.stdout == "Chassis Power is on\n":
            return True
        else:
            raise ValueError(f"Got unexpected IPMI power status: '{output}'")
