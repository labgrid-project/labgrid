# pylint: disable=no-member
import attr
import subprocess
import os.path

from ..factory import target_factory
from ..protocol import BootstrapProtocol
from ..resource.remote import NetworkAlteraUSBBlaster
from ..resource.udev import AlteraUSBBlaster
from ..step import step
from .common import Driver, check_file


@target_factory.reg_driver
@attr.s(cmp=False)
class OpenOCDDriver(Driver, BootstrapProtocol):
    bindings = {
        "interface": {AlteraUSBBlaster, NetworkAlteraUSBBlaster},
    }

    config = attr.ib(validator=attr.validators.instance_of(str))
    search = attr.ib(default=None, validator=attr.validators.optional(attr.validators.instance_of(str)))
    image = attr.ib(default=None, validator=attr.validators.optional(attr.validators.instance_of(str)))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        # FIXME make sure we always have an environment or config
        if self.target.env:
            self.tool = self.target.env.config.get_tool('openocd') or 'openocd'
            self.config = self.target.env.config.resolve_path(self.config)
            if self.search:
                self.search = self.target.env.config.resolve_path(self.search)
        else:
            self.tool = 'openocd'

    @Driver.check_active
    @step(args=['filename'])
    def load(self, filename=None):
        if filename is None and self.image is not None:
            filename = self.target.env.config.get_image_path(self.image)
        filename = os.path.abspath(os.path.expanduser(filename))
        check_file(self.config, command_prefix=self.interface.command_prefix)
        check_file(filename, command_prefix=self.interface.command_prefix)
        cmd = self.interface.command_prefix+[self.tool]
        if self.search:
            cmd += ["--search", self.search]
        cmd += [
            "--file", self.config,
            "--command", "'init'",
            "--command", "'bootstrap {}'".format(filename),
            "--command", "'shutdown'",
        ]
        subprocess.check_call(cmd)
