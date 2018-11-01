# pylint: disable=no-member
import subprocess
import logging
from itertools import chain
import attr

from ..factory import target_factory
from ..protocol import BootstrapProtocol
from ..resource.remote import NetworkAlteraUSBBlaster
from ..resource.udev import AlteraUSBBlaster
from ..step import step
from ..util.managedfile import ManagedFile
from .common import Driver, check_file


@target_factory.reg_driver
@attr.s(cmp=False)
class OpenOCDDriver(Driver, BootstrapProtocol):
    bindings = {
        "interface": {AlteraUSBBlaster, NetworkAlteraUSBBlaster},
    }

    config = attr.ib(validator=attr.validators.instance_of((str, list)))
    search = attr.ib(
        default=[],
        validator=attr.validators.optional(attr.validators.instance_of((str, list)))
    )
    image = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str))
    )

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.logger = logging.getLogger("{}:{}".format(self, self.target))
        self.config = self.resolve_path_str_or_list(self.config)
        self.search = self.resolve_path_str_or_list(self.search)

        # FIXME make sure we always have an environment or config
        if self.target.env:
            self.tool = self.target.env.config.get_tool('openocd') or 'openocd'
        else:
            self.tool = 'openocd'

    def resolve_path_str_or_list(self, path):
        if isinstance(path, str):
            if self.target.env:
                return [self.target.env.config.resolve_path(path)]
            return [path]

        elif isinstance(path, list):
            if self.target.env:
                return [self.target.env.config.resolve_path(p) for p in path]
            # fall-through

        return path

    @Driver.check_active
    @step(args=['filename'])
    def load(self, filename=None):
        if filename is None and self.image is not None:
            filename = self.target.env.config.get_image_path(self.image)
        mf = ManagedFile(filename, self.interface)
        mf.sync_to_resource()

        managed_configs = []
        for config in self.config:
            mconfig = ManagedFile(config, self.interface)
            mconfig.sync_to_resource()
            managed_configs.append(mconfig)

        cmd = self.interface.command_prefix+[self.tool]
        cmd += chain.from_iterable(("--search", path) for path in self.search)

        for mconfig in managed_configs:
            cmd.append("--file")
            cmd.append(mconfig.get_remote_path())

        cmd += [
            "--command", "'init'",
            "--command", "'bootstrap {}'".format(mf.get_remote_path()),
            "--command", "'shutdown'",
        ]
        subprocess.check_call(cmd)

    @Driver.check_active
    @step(args=['commands'])
    def execute(self, commands: list):
        managed_configs = []
        for config in self.config:
            mconfig = ManagedFile(config, self.interface)
            mconfig.sync_to_resource()
            managed_configs.append(mconfig)

        cmd = self.interface.command_prefix+[self.tool]
        cmd += chain.from_iterable(("--search", path) for path in self.search)

        for mconfig in managed_configs:
            cmd.append("--file")
            cmd.append(mconfig.get_remote_path())

        cmd += chain.from_iterable(("--command", "'{}'".format(command)) for command in commands)
        subprocess.check_call(cmd)
