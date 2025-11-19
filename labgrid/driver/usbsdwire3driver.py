import subprocess

import attr

from .common import Driver
from ..factory import target_factory
from ..step import step
from .exception import ExecutionError
from ..util.helper import processwrapper

@target_factory.reg_driver
@attr.s(eq=False)
class USBSDWire3Driver(Driver):
    """The USBSDWire3Driver uses the sdwire tool to control SDWire hardware

    Args:
        bindings (dict): driver to use with usbsdmux
    """
    bindings = {
        "mux": {"USBSDWire3Device", "NetworkUSBSDWire3Device"},
    }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        print(f"USBSDWire3Driver __attrs_post_init__ called for {self.mux}")
        if self.target.env:
            self.tool = self.target.env.config.get_tool('sdwire')
        else:
            self.tool = 'sdwire'
        if self.mux.control_serial is None:
            raise ExecutionError("USBSDWire3Driver requires 'control_serial' to be set in the resource")
        self.control_serial = self.match_control_serial()
        print(f"USBSDWire3Driver __attrs_post_init__ control_serial: {self.control_serial}")

    @Driver.check_active
    @step(title='sdmux_set', args=['mode'])
    def set_mode(self, mode):
        if not mode.lower() in ['dut', 'host']:
            raise ExecutionError(f"Setting mode '{mode}' not supported by USBSDWire3Driver")
        cmd = self.mux.command_prefix + [
            self.tool,
            "switch",
            "-s",
            self.control_serial,
            "dut" if mode.lower() == "dut" else "ts",
        ]
        print(f"USBSDWire3Driver set_mode executing: {' '.join(cmd)}")
        processwrapper.check_output(cmd)

    def match_control_serial(self):
        cmd = self.mux.command_prefix + [
            self.tool,
            "list"
        ]
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            check=True
        )
        output = proc.stdout.strip().decode()
        for line in output.splitlines():
            if self.mux.control_serial is not None and line.find(self.mux.control_serial) >= 0:
                return line.split()[0]
        raise ExecutionError(f"Could not find control serial {self.mux.control_serial} in sdwire list output")

    @Driver.check_active
    @step(title='sdmux_get')
    def get_mode(self):
        raise ExecutionError("Getting mode not supported by USBSDWire3Driver")
