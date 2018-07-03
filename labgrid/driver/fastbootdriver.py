# pylint: disable=no-member
import subprocess
import os.path
import attr

from ..factory import target_factory
from ..resource.remote import NetworkAndroidFastboot
from ..resource.udev import AndroidFastboot
from ..step import step
from .common import Driver, check_file


@target_factory.reg_driver
@attr.s(cmp=False)
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

    def _get_fastboot_prefix(self):
        return self.fastboot.command_prefix+[
            self.tool,
            "-i", hex(self.fastboot.vendor_id),
            "-s", "usb:{}".format(self.fastboot.path),
        ]

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass

    @Driver.check_active
    @step(title='call', args=['args'])
    def __call__(self, *args):
        subprocess.check_call(self._get_fastboot_prefix() + list(args))

    @Driver.check_active
    @step(args=['filename'])
    def boot(self, filename):
        filename = os.path.abspath(filename)
        check_file(filename, command_prefix=self.fastboot.command_prefix)
        self("boot", filename)

    @Driver.check_active
    @step(args=['partition', 'filename'])
    def flash(self, partition, filename):
        filename = os.path.abspath(filename)
        check_file(filename, command_prefix=self.fastboot.command_prefix)
        self("flash", partition, filename)

    @Driver.check_active
    @step(args=['cmd'])
    def run(self, cmd):
        self("oem", "exec", "--", cmd)

    @Driver.check_active
    @step(title='continue')
    def continue_boot(self):
        self("continue")
