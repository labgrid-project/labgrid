# pylint: disable=no-member
import logging
import subprocess
import os
import attr

from ..factory import target_factory
from ..resource.udev import USBMassStorage, USBSDMuxDevice
from ..resource.remote import NetworkUSBMassStorage, NetworkUSBSDMuxDevice
from ..step import step
from ..util.managedfile import ManagedFile
from .common import Driver
from ..driver.exception import ExecutionError


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
        if not self.storage.path:
            raise ExecutionError(
                "{} is not available".format(self.storage_path)
            )
        mf = ManagedFile(filename, self.storage)
        mf.sync_to_resource()
        self.logger.info("pwd: %s", os.getcwd())
        args = [
            "dd",
            "if={}".format(mf.get_remote_path()),
            "of={} status=progress bs=4M conv=fdatasync"
            .format(self.storage.path)
        ]
        subprocess.check_call(
            self.storage.command_prefix + args
        )

    @step(result=True)
    def get_size(self):
        if not self.storage.path:
            raise ExecutionError(
                "{} is not available".format(self.storage_path)
            )
        args = ["cat", "/sys/class/block/{}/size" % self.storage.path[5:]]
        size = subprocess.check_output(self.storage.command_prefix + args)
        return int(size)
