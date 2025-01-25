import attr

from ..factory import target_factory
from ..protocol import BootstrapProtocol
from ..step import step
from ..util.managedfile import ManagedFile
from ..util.helper import processwrapper
from .common import Driver


@target_factory.reg_driver
@attr.s(eq=False)
class OpenFPGALoaderDriver(Driver, BootstrapProtocol):
    """OpenFPGALoaderDriver - Driver to bootstrap FPGA boards with a bitstream file

    Arguments:
        image (str): optional, the default bitstream image file if not specified when calling load()
        board (str): optional, the FPGA board identifier
        frequency (int): optional, force a non-default programmer frequency in Hz
    """
    bindings = {
        "interface": {
            "AlteraUSBBlaster", "NetworkAlteraUSBBlaster",
            "USBDebugger", "NetworkUSBDebugger",
        },
    }

    image = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str))
    )
    board = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str))
    )
    frequency = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(int))
    )

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

        if self.target.env:
            self.tool = self.target.env.config.get_tool('openfpgaloader')
        else:
            self.tool = 'openFPGALoader'

    @Driver.check_active
    @step(args=['filename'])
    def load(self, filename=None):
        cmd = [self.tool]

        if filename is None and self.image is not None:
            filename = self.target.env.config.get_image_path(self.image)
        mf = ManagedFile(filename, self.interface)
        mf.sync_to_resource()
        cmd += ["--bitstream", mf.get_remote_path()]

        cmd += ["--busdev-num", f"{self.interface.busnum}:{self.interface.devnum}"]

        if self.board:
            cmd += ["--board", self.board]

        if self.frequency:
            cmd += ["--freq", str(self.frequency)]

        processwrapper.check_output(
            self.interface.wrap_command(cmd),
            print_on_silent_log=True
        )
