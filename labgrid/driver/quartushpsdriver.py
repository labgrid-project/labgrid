# pylint: disable=no-member
import subprocess
import os.path
import re
import attr

from ..factory import target_factory
from ..resource.remote import NetworkAlteraUSBBlaster
from ..resource.udev import AlteraUSBBlaster
from ..step import step
from .common import Driver, check_file
from .exception import ExecutionError


@target_factory.reg_driver
@attr.s(cmp=False)
class QuartusHPSDriver(Driver):
    bindings = {
        "interface": {AlteraUSBBlaster, NetworkAlteraUSBBlaster},
    }

    image = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str))
    )
    cable_number = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str))
    )

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        # FIXME make sure we always have an environment or config
        if self.target.env:
            self.tool = self.target.env.config.get_tool('quartus_hps') or 'quartus_hps'
        else:
            self.tool = 'quartus_hps'

    def on_deactivate(self):
        # forget cable number as it might change
        self.cable_number = None

    def _get_cable_number(self):
        """Returns the JTAG cable numer for the USB path of the device"""
        # FIXME make sure we always have an environment or config
        if self.target.env:
            jtagconfig_tool = self.target.env.config.get_tool('jtagconfig') or 'jtagconfig'
        else:
            jtagconfig_tool = 'jtagconfig'

        cmd = self.interface.command_prefix + [jtagconfig_tool]
        jtagconfig_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE
        )
        stdout, _ = jtagconfig_process.communicate()

        regex = re.compile(r".*(\d+)\) .* \[(.*)\]")
        for line in stdout.decode("utf-8").split("\n"):
            jtag_mapping = regex.match(line)
            if jtag_mapping:
                cable_number, usb_path = jtag_mapping.groups()
                if usb_path == self.interface.path:
                    return int(cable_number)

        raise ExecutionError("Could not get cable number for USB path {}"
                             .format(self.interface.path))

    @Driver.check_active
    @step(args=['filename', 'address'])
    def flash(self, filename=None, address=0x0):
        if filename is None and self.image is not None:
            filename = self.target.env.config.get_image_path(self.image)
        filename = os.path.abspath(os.path.expanduser(filename))
        check_file(filename, command_prefix=self.interface.command_prefix)

        assert isinstance(address, int)

        if self.cable_number is None:
            self.cable_number = self._get_cable_number()

        cmd = self.interface.command_prefix + [self.tool]
        cmd += [
            "--cable={}".format(self.cable_number),
            "--addr=0x{:X}".format(address),
            "--operation=P {}".format(filename),
        ]
        subprocess.check_call(cmd)
