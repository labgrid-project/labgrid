# pylint: disable=no-member
import logging
import os
from time import time
import attr

from ..factory import target_factory
from ..resource.udev import USBMassStorage, USBSDMuxDevice
from ..step import step
from .common import Driver


@target_factory.reg_driver
@attr.s(cmp=False)
class USBStorageDriver(Driver):
    bindings = {"storage": {USBMassStorage, USBSDMuxDevice}, }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.logger = logging.getLogger("{}:{}".format(self, self.target))

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass

    @step(args=['filename'])
    def write_image(self, filename):
        with open(filename, 'rb') as src, \
                open(self.storage.path, 'wb') as dst:
            src.seek(0, os.SEEK_END)
            size = src.tell()
            src.seek(0, os.SEEK_SET)

            count = 0
            stat = time() + 3
            while True:
                data = src.read(1024*1024)
                if not data:
                    break
                dst.write(data)
                dst.flush()
                os.fsync(dst.fileno())
                count += len(data)
                if time() > stat:
                    stat += 3
                    self.logger.info("writing image %.0f%%", count*100/size)
            dst.flush()
            os.fsync(dst.fileno())

    @step(result=True)
    def get_size(self):
        with open(self.storage.path, 'rb') as dst:
            dst.seek(0, os.SEEK_END)
            size = dst.tell()
        return size
