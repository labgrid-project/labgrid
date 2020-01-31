# pylint: disable=no-member
import logging
from itertools import chain
import attr

from ..factory import target_factory
from ..protocol import BootstrapProtocol
from ..step import step
from ..util.managedfile import ManagedFile
from ..util.helper import processwrapper
from .common import Driver


@target_factory.reg_driver
@attr.s(eq=False)
class OpenOCDDriver(Driver, BootstrapProtocol):
    bindings = {
        "interface": {"AlteraUSBBlaster", "NetworkAlteraUSBBlaster"},
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

        # FIXME make sure we always have an environment or config
        if self.target.env:
            self.tool = self.target.env.config.get_tool('openocd') or 'openocd'
            self.config = self.target.env.config.resolve_path_str_or_list(self.config)
            self.search = self.target.env.config.resolve_path_str_or_list(self.search)
        else:
            self.tool = 'openocd'
            if isinstance(self.config, str):
                self.config = [self.config]
            if isinstance(self.search, str):
                self.search = [self.search]

    def _get_usb_path_cmd(self):
        # OpenOCD supports "adapter usb location" since a1b308ab, if the command is not known
        # notice user and continue
        message = ("Your OpenOCD version does not support specifying USB paths.\n"
                   "Consider updating to OpenOCD master when using multiple USB Blasters.")
        return [
            "--command",
            "'if {{ [catch {{adapter usb location \"{usbpath}\"}}] }} {{ puts stderr \"{msg}\" }}'"
            .format(usbpath=self.interface.path, msg=message)
        ]

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

        cmd += self._get_usb_path_cmd()
        cmd += [
            "--command", "'init'",
            "--command", "'bootstrap {}'".format(mf.get_remote_path()),
            "--command", "'shutdown'",
        ]
        processwrapper.check_output(cmd)

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
        cmd += self._get_usb_path_cmd()

        for mconfig in managed_configs:
            cmd.append("--file")
            cmd.append(mconfig.get_remote_path())

        cmd += chain.from_iterable(("--command", "'{}'".format(command)) for command in commands)
        processwrapper.check_output(cmd)
