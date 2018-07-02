# pylint: disable=no-member
import subprocess
import os.path
import logging
from itertools import chain
import attr

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
        filename = os.path.abspath(os.path.expanduser(filename))

        check_file(filename, command_prefix=self.interface.command_prefix)
        for config in self.config:
            check_file(config, command_prefix=self.interface.command_prefix)

        cmd = self.interface.command_prefix+[self.tool]
        cmd += chain.from_iterable(("--search", path) for path in self.search)
        cmd += chain.from_iterable(("--file", path) for path in self.config)
        cmd += [
            "--command", "'init'",
            "--command", "'bootstrap {}'".format(filename),
            "--command", "'shutdown'",
        ]
        subprocess.check_call(cmd)

    @Driver.check_active
    @step(args=['commands'])
    def execute(self, commands: list):
        for config in self.config:
            check_file(config, command_prefix=self.interface.command_prefix)

        cmd = self.interface.command_prefix+[self.tool]
        cmd += chain.from_iterable(("--search", path) for path in self.search)
        cmd += chain.from_iterable(("--file", conf) for conf in self.config)
        cmd += chain.from_iterable(("--command", "'{}'".format(command)) for command in commands)
        subprocess.check_call(cmd)
