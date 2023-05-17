import attr

from .common import Driver
from ..factory import target_factory
from ..step import step
from .exception import ExecutionError
from ..util.helper import processwrapper

@target_factory.reg_driver
@attr.s(eq=False)
class USBSDWireDriver(Driver):
    """The USBSDWireDriver uses the sd-mux-ctrl tool to control SDWire hardware

    Args:
        bindings (dict): driver to use with usbsdmux
    """
    bindings = {
        "mux": {"USBSDWireDevice", "NetworkUSBSDWireDevice"},
    }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.target.env:
            self.tool = self.target.env.config.get_tool('sd-mux-ctrl')
        else:
            self.tool = 'sd-mux-ctrl'

    @Driver.check_active
    @step(title='sdmux_set', args=['mode'])
    def set_mode(self, mode):
        if not mode.lower() in ['dut', 'host']:
            raise ExecutionError(f"Setting mode '{mode}' not supported by USBSDWireDriver")
        cmd = self.mux.command_prefix + [
            self.tool,
            '--dut' if mode.lower() == "dut" else "--ts",
            "-e",
            self.mux.control_serial,
        ]
        processwrapper.check_output(cmd)

    @Driver.check_active
    @step(title='sdmux_get')
    def get_mode(self):
        cmd = self.mux.command_prefix + [
            self.tool,
            "-e",
            self.mux.control_serial,
            "-u",
        ]
        result = processwrapper.check_output(cmd)
        return result.split(b": ", maxsplit=1)[1].strip().decode()
