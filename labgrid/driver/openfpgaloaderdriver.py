import attr

from ..factory import target_factory
from ..protocol import BootstrapProtocol
from ..step import step
from ..util.helper import processwrapper
from ..util.managedfile import ManagedFile
from .common import Driver


@target_factory.reg_driver
@attr.s(eq=False)
class OpenFPGALoaderDriver(Driver, BootstrapProtocol):
    """OpenFPGALoaderDriver - Driver to bootstrap FPGA boards with a bitstream file

    Arguments:
        image (str): optional, key in images containing the path of the bitstream, used if no
            filename is passed to load()
        board (str): optional, the FPGA board identifier
        frequency (int): optional, force a non-default programmer frequency in Hz
    """

    bindings = {
        "interface": {
            "AlteraUSBBlaster",
            "NetworkAlteraUSBBlaster",
            "USBDebugger",
            "NetworkUSBDebugger",
        },
    }

    image = attr.ib(default=None, validator=attr.validators.optional(attr.validators.instance_of(str)))
    board = attr.ib(default=None, validator=attr.validators.optional(attr.validators.instance_of(str)))
    frequency = attr.ib(default=None, validator=attr.validators.optional(attr.validators.instance_of(int)))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

        if self.target.env:
            self.tool = self.target.env.config.get_tool("openFPGALoader")
        else:
            self.tool = "openFPGALoader"

    @Driver.check_active
    @step(args=["filename"])
    def load(self, filename=None):
        cmd = [self.tool]

        if filename is None and self.image is not None:
            filename = self.target.env.config.get_image_path(self.image)
        if filename is None:
            raise ValueError("No bitstream given: pass a filename to load() or set the image attribute")
        mf = ManagedFile(filename, self.interface)
        mf.sync_to_resource()
        cmd += ["--bitstream", mf.get_remote_path()]

        cmd += ["--busdev-num", f"{self.interface.busnum}:{self.interface.devnum}"]

        if self.board:
            cmd += ["--board", self.board]

        if self.frequency:
            cmd += ["--freq", str(self.frequency)]

        processwrapper.check_wrapped_output(self.interface, cmd, print_on_silent_log=True)
