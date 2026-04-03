import attr

from .common import Driver
from ..factory import target_factory
from ..step import step
from .exception import ExecutionError
from ..util.helper import processwrapper

@target_factory.reg_driver
@attr.s(eq=False)
class USBSDWireBadgerdDriver(Driver):
    """The USBSDWireDriver uses the sd-mux-ctrl tool to control SDWire hardware

    Args:
        bindings (dict): driver to use with usbsdmux
    """
    bindings = {
        "mux": {"USBSDWireBadgerdDevice", "NetworkUSBSDWireBadgerdDevice"},
    }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.target.env:
            self.tool = self.target.env.config.get_tool('sdwire')
        else:
            self.tool = 'sdwire'

    @Driver.check_active
    @step(title='sdmux_set', args=['mode'])
    def set_mode(self, mode):
        if not mode.lower() in ['dut', 'host']:
            raise ExecutionError(f"Setting mode '{mode}' not supported by USBSDWireBadgerdDevice")
        cmd = self.mux.command_prefix + [
            self.tool,
            'switch',
            "-s",
            self.mux.control_serial + '.3.3.2',
            'dut' if mode.lower() == "dut" else "host",
        ]
        processwrapper.check_output(cmd)

    @Driver.check_active
    @step(title='sdmux_get')
    def get_mode(self):
        return 'unknown'
