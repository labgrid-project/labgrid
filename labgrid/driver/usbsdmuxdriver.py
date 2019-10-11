# pylint: disable=no-member
import attr

from .common import Driver
from ..factory import target_factory
from ..step import step
from .exception import ExecutionError
from ..util.helper import processwrapper

@target_factory.reg_driver
@attr.s(eq=False)
class USBSDMuxDriver(Driver):
    """The USBSDMuxDriver uses the usbsdmux tool
    (https://github.com/pengutronix/usbsdmux) to control the USB-SD-Mux
    hardware

    Args:
        bindings (dict): driver to use with usbsdmux
    """
    bindings = {
        "mux": {"USBSDMuxDevice", "NetworkUSBSDMuxDevice"},
    }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.target.env:
            self.tool = self.target.env.config.get_tool('usbsdmux') or 'usbsdmux'
        else:
            self.tool = 'usbsdmux'

    @Driver.check_active
    @step(title='sdmux_set', args=['mode'])
    def set_mode(self, mode):
        if not mode.lower() in ['dut', 'host', 'off', 'client']:
            raise ExecutionError("Setting mode '%s' not supported by USBSDMuxDriver" % mode)
        cmd = self.mux.command_prefix + [
            self.tool,
            "-c",
            self.mux.control_path,
            mode.lower()
        ]
        processwrapper.check_output(cmd)
