# pylint: disable=no-member
import attr
import subprocess
import os.path

from ..factory import target_factory
from ..resource.remote import NetworkAndroidFastboot
from ..resource.udev import AndroidFastboot
from ..step import step
from .common import Driver, check_file
from .exception import ExecutionError


@target_factory.reg_driver
@attr.s
class AndroidFastbootDriver(Driver):
    bindings = {
        "fastboot": {AndroidFastboot, NetworkAndroidFastboot},
    }

    image = attr.ib(default=None)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        # FIXME make sure we always have an environment or config
        if self.target.env:
            self.tool = self.target.env.config.get_tool('fastboot') or 'fastboot'
        else:
            self.tool = 'fastboot'
        self.prefix = self.fastboot.command_prefix+[
            self.tool,
            "-i", hex(self.fastboot.vendor_id),
            "-s", "usb:{}".format(self.fastboot.path),
        ]

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass

    @step(args=['args'])
    def __call__(self, *args):
        subprocess.check_call(self.prefix + list(args))

    @step(args=['filename'])
    def boot(self, filename):
        filename = os.path.abspath(filename)
        check_file(filename, command_prefix=self.prefix)
        self("boot", filename)

    @step(args=['partition', 'filename'])
    def flash(self, partition, filename):
        filename = os.path.abspath(filename)
        check_file(filename, command_prefix=self.prefix)
        self("flash", partition, filename)
