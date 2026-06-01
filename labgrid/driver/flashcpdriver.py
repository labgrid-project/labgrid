import os
from uuid import uuid4
from pathlib import Path

import attr
from .common import check_file
from .exception import ExecutionError
from ..factory import target_factory
from ..step import step
from ..driver import Driver
from ..protocol import BootstrapProtocol, FileTransferProtocol, CommandProtocol
from ..util.helper import processwrapper


@target_factory.reg_driver
@attr.s(eq=False)
class FlashcpDriver(Driver, BootstrapProtocol):
    _devfs: Path = Path("/dev")

    bindings = {
        "mtdpartition": {"DevfsMTDPartition", "NetworkDevfsMTDPartition"},
        "filetransfer": FileTransferProtocol,
        "command": CommandProtocol
    }

    image = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str)),
    )
    tool = attr.ib(
        default="flashcp",
        validator=attr.validators.instance_of(str),
    )

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    def _get_flashcp_prefix(self):
        return self.mtdpartition.command_prefix + [self.tool]

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass

    @Driver.check_active
    @step(title="call", args=["args"])
    def __call__(self, *args):
        arg_list = list(args)
        arg_list.append("-v")
        processwrapper.check_output(
            self._get_flashcp_prefix() + arg_list, print_on_silent_log=True
        )

    @Driver.check_active
    @step(result=True, args=["filename"])
    def load(self, filename=None):
        if filename is None and self.image is not None:
            filename = self.target.env.config.get_image_path(self.image)
        elif filename is None and self.image is None:
            raise ExecutionError(
                "At least one of 'filename' argument or driver 'image' attribute must supplied."
            )
        filename = os.path.abspath(filename)
        check_file(filename)
        remote_folder = Path(f"/tmp/image-{uuid4()}")
        remote_file = remote_folder.joinpath(Path(filename).name)

        self.command.run_check(f"mkdir -p {remote_folder.as_posix()}")
        self.filetransfer.put(filename, remote_file.as_posix())
        self.logger.info("Local File %s put to remote path %s", filename, remote_file)
        self.logger.info("Now flashing to mtd partition '%i'", self.mtdpartition.index)
        self(
            remote_file.as_posix(),
            self._devfs.joinpath(f"mtd{self.mtdpartition.index}").as_posix(),
        )
        self.logger.info("Flashing finished.")
