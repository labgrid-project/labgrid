# pylint: disable=no-member
import logging
import subprocess
import os
import attr

from ..factory import target_factory
from ..resource.udev import USBMassStorage, USBSDMuxDevice
from ..resource.remote import NetworkUSBMassStorage, NetworkUSBSDMuxDevice
from ..step import step
from .common import Driver, check_file

@target_factory.reg_driver
@attr.s(cmp=False)
class NetworkUSBStorageDriver(Driver):
    bindings = {
        "storage": {
            USBMassStorage,
            NetworkUSBMassStorage,
            USBSDMuxDevice,
            NetworkUSBSDMuxDevice
        },
    }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.logger = logging.getLogger("{}:{}".format(self, self.target))

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass

    @step(args=['filename'])
    def write_image(self, filename):
        filename = os.path.abspath(filename)
        check_file(filename, command_prefix=self.storage.command_prefix)
        self.logger.info("pwd: %s", os.getcwd())
        args = [
            "dd",
            "if={}".format(filename),
            "of={} status=progress bs=4M conv=fdatasync"
            .format(self.storage.path)
        ]
        subprocess.check_call(
            self.storage.command_prefix + args
        )

    @step(result=True)
    def get_size(self):
        args = ["cat", "/sys/class/block/{}/size" % self.storage.path[5:]]
        size = subprocess.check_output(self.storage.command_prefix + args)
        return int(size)
