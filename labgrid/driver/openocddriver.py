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
        "interface": {
            "AlteraUSBBlaster", "NetworkAlteraUSBBlaster",
            "USBDebugger", "NetworkUSBDebugger",
        },
    }

    config = attr.ib(
        default=attr.Factory(list),
        validator=attr.validators.optional(attr.validators.instance_of((str, list)))
    )
    search = attr.ib(
        default=attr.Factory(list),
        validator=attr.validators.optional(attr.validators.instance_of((str, list)))
    )
    image = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str))
    )
    interface_config = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str))
    )
    board_config = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str))
    )
    load_commands = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(list))
    )

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

        # FIXME make sure we always have an environment or config
        if self.target.env:
            self.tool = self.target.env.config.get_tool('openocd')
            self.config = self.target.env.config.resolve_path_str_or_list(self.config)
            self.search = self.target.env.config.resolve_path_str_or_list(self.search)
        else:
            self.tool = 'openocd'
            if isinstance(self.config, str):
                self.config = [self.config]
            if isinstance(self.search, str):
                self.search = [self.search]

    def _get_usb_path_cmd(self):
        # OpenOCD supports "adapter usb location" since a1b308ab, released with 0.11.0-rc1
        return ["--command", f"adapter usb location \"{self.interface.path}\""]

    def _run_commands(self, commands: list):
        cmd = [self.tool]
        cmd += chain.from_iterable(("--search", path) for path in self.search)
        cmd += self._get_usb_path_cmd()

        managed_configs = []
        for config in self.config:
            mconfig = ManagedFile(config, self.interface)
            mconfig.sync_to_resource()
            managed_configs.append(mconfig)

        if self.interface_config:
            cmd.append("--file")
            cmd.append(f"interface/{self.interface_config}")

        if self.board_config:
            cmd.append("--file")
            cmd.append(f"board/{self.board_config}")

        for mconfig in managed_configs:
            cmd.append("--file")
            cmd.append(mconfig.get_remote_path())

        cmd += chain.from_iterable(("--command", f"{command}") for command in commands)
        processwrapper.check_output(
            self.interface.wrap_command(cmd),
            print_on_silent_log=True
        )

    @Driver.check_active
    @step(args=['filename'])
    def load(self, filename=None):
        if filename is None and self.image is not None:
            filename = self.target.env.config.get_image_path(self.image)
        mf = ManagedFile(filename, self.interface)
        mf.sync_to_resource()

        if self.load_commands is None:
            commands = [
                "init",
                f"bootstrap {mf.get_remote_path()}",
                "shutdown",
            ]
        else:
            commands = [c.format(filename=mf.get_remote_path()) for c in self.load_commands]

        self._run_commands(commands)

    @Driver.check_active
    @step(args=['commands'])
    def execute(self, commands: list):
        self._run_commands(commands)
