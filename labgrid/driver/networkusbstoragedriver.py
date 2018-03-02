# pylint: disable=no-member
import attr
import subprocess
import os

from ..factory import target_factory
from ..resource.udev import USBMassStorage
from ..resource.remote import NetworkUSBMassStorage
from ..step import step
from .common import Driver, check_file

@target_factory.reg_driver
@attr.s(cmp=False)
class NetworkUSBStorageDriver(Driver):
    bindings = {"storage": {USBMassStorage, NetworkUSBMassStorage}, }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass

    @step(args=['filename'])
    def write_image(self, filename):
        filename = os.path.abspath(filename)
        check_file(filename, command_prefix=self.storage.command_prefix)
        print("pwd: %s" % os.getcwd())
        subprocess.check_call(
          self.storage.command_prefix+["dd", "if=%s" % filename, "of=%s status=progress bs=4M conv=fdatasync" % self.storage.path]
        )

    @step(result=True)
    def get_size(self):
        size = subprocess.check_output(
          self.storage.command_prefix+["cat", "/sys/class/block/%s/size" % self.storage.path[5:]]
        )
        return int(size)
