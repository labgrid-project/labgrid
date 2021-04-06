# pylint: disable=no-member
import attr

from .common import Driver
from ..factory import target_factory
from ..step import step
from .exception import ExecutionError
from ..util.helper import processwrapper

@target_factory.reg_driver
@attr.s(eq=False)
class LXAUSBMuxDriver(Driver):
    """The LXAUSBMuxDriver uses the usbmuxctl tool to control the USBMux
    hardware
    """
    bindings = {
        "mux": {"LXAUSBMux", "NetworkLXAUSBMux"},
    }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.target.env:
            self.tool = self.target.env.config.get_tool('usbmuxctl') or 'usbmuxctl'
        else:
            self.tool = 'usbmuxctl'

    @Driver.check_active
    @step(title='usbmux_set', args=['links'])
    def set_links(self, links):
        args = []
        for link in links:
            link = link.lower()
            if link == 'dut-device':
                args.append('--dut-device')
            elif link == 'host-dut':
                args.append('--host-dut')
            elif link == 'host-device':
                args.append('--host-device')
            else:
                raise ExecutionError("Link '%s' not supported by LXAUSBMuxDriver" % link)

        cmd = self.mux.command_prefix + [
            self.tool,
            "--path",
            self.mux.path,
            "connect",
            *args,
        ]
        processwrapper.check_output(cmd)
