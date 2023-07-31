"Xilinx System Debugger (XSDB) driver"
import logging
import subprocess

import attr

from .common import Driver
from ..factory import target_factory
from ..resource.udev import XilinxUSBJTAG
from ..resource.remote import NetworkXilinxUSBJTAG
from ..step import step
from ..util.helper import processwrapper


@target_factory.reg_driver
@attr.s(eq=False)
class XSDBDriver(Driver):
    bindings = {
        "interface": {XilinxUSBJTAG, NetworkXilinxUSBJTAG},
    }

    bitstream = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str))
    )

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.logger = logging.getLogger("{}({})".format(self, self.target))

        # FIXME make sure we always have an environment or config
        if self.target.env:
            self.xsdb_bin = self.target.env.config.get_tool('xsdb') or 'xsdb'
        else:
            self.xsdb_bin = 'xsdb'

    @Driver.check_active
    @step(args=['tcl_cmds', 'interactive'])
    def run(self, tcl_cmds, interactive=False):
        url = self.interface.agent_url.split(":")
        if not url[1]:
            url[1] = self.interface.host

        tcl_cmd = "connect -url {}; ".format(":".join(url))
        tcl_cmd += "; ".join(tcl_cmds)

        cmd = [self.xsdb_bin, "-eval", tcl_cmd]
        if interactive:
            cmd.append('-interactive')

        # Do not use ProcessWrapper because it garbles output up
        self.logger.debug("Running command: %s", cmd)
        subprocess.run(cmd, check=True)

    @Driver.check_active
    @step(args=['filename'])
    def program_bitstream(self, filename):
        if filename is None and self.bitstream is not None:
            filename = self.target.env.config.get_image_path(self.bitstream)

        self.run(["fpga {}".format(filename)])
