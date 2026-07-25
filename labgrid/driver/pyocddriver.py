import attr

from ..factory import target_factory
from ..protocol import BootstrapProtocol, ResetProtocol
from ..step import step
from ..util.managedfile import ManagedFile
from ..util.helper import processwrapper
from .common import Driver


@target_factory.reg_driver
@attr.s(eq=False)
class PyOCDDriver(Driver, BootstrapProtocol, ResetProtocol):

    priorities = {ResetProtocol: 5}

    bindings = {
        "interface": {
            "USBDebugger",
            "NetworkUSBDebugger",
        },
    }

    image = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str)),
    )
    load_commands = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of((str, list))),
    )
    target_name = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str)),
    )
    frequency = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str)),
    )
    config = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str)),
    )
    serial = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str)),
    )

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

        # FIXME make sure we always have an environment or config
        if self.target.env:
            self.tool = self.target.env.config.get_tool("pyocd")
            if self.config:
                self.config = self.target.env.config.resolve_path(self.config)
        else:
            self.tool = "pyocd"

    def _run_commands(self, subcommand: str, commands: list | None = None):
        cmd = [self.tool, subcommand]
        if self.serial:
            cmd += ["--uid", self.serial]
        if self.target_name is not None and (not commands or "--target" not in commands):
            cmd += ["--target", self.target_name]
        if self.frequency is not None and (not commands or "--frequency" not in commands):
            cmd += ["--frequency", self.frequency]

        if self.config is not None:
            mconfig = ManagedFile(self.config, self.interface)
            mconfig.sync_to_resource()
            cmd += ["--config", mconfig.get_remote_path()]
        else:
            cmd += ["--no-config"]

        if commands:
            cmd += commands
        processwrapper.check_output(
            command=self.interface.wrap_command(cmd),
            print_on_silent_log=True,
        )

    @Driver.check_active
    @step(args=["filename"])
    def load(self, filename=None):

        if filename is None and self.image is not None and self.target.env:
            filename = self.target.env.config.get_image_path(self.image)

        mf = ManagedFile(filename, self.interface)
        mf.sync_to_resource()

        if self.load_commands:
            if isinstance(self.load_commands, str):
                commands = self.load_commands.split()
            else:
                commands = self.load_commands
        else:
            commands = ["-e", "sector"]

        commands.append(mf.get_remote_path())

        self._run_commands("load", commands)

    @Driver.check_active
    @step()
    def reset(self):
        self._run_commands("reset")
