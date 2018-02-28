# pylint: disable=no-member
import attr
import subprocess

from labgrid.factory import target_factory
from labgrid.driver.common import Driver
from ..resource.udev import USBSDMuxDevice

@target_factory.reg_driver
@attr.s(cmp=False)
class USBSDMuxDriver(Driver):
    """The USBSDMuxDriver uses the usbsdmux tool
    (https://github.com/pengutronix/usbsdmux) to control the USB-SD-Mux
    hardware

    Args:
        bindings (dict): driver to use with usbsdmux
    """
    bindings = {
        "mux": {USBSDMuxDevice},
    }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.target.env:
            self.tool = self.target.env.config.get_tool('usbsdmux') or 'usbsdmux'
        else:
            self.tool = 'usbsdmux'

    @Driver.check_active
    def set_mode(self, mode):
        ''
        if not mode.lower() in ['dut', 'host', 'off', 'client']:
            raise ExecutionError("Setting mode '%s' not supported by USBSDMuxDriver" % mode)
        cmd = [
                self.tool,
                "-c",
                self.mux.control_path,
                mode.lower()
        ]
        subprocess.check_call(cmd)
