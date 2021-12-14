# pylint: disable=no-member
import enum
import logging
import os
import time
import subprocess

import attr

from ..factory import target_factory
from ..step import step
from ..util.managedfile import ManagedFile
from .common import Driver
from ..driver.exception import ExecutionError

from ..util.helper import processwrapper
from ..util import Timeout


class Mode(enum.Enum):
    DD = "dd"
    BMAPTOOL = "bmaptool"

    def __str__(self):
        return self.value


@target_factory.reg_driver
@attr.s(eq=False)
class USBStorageDriver(Driver):
    bindings = {
        "storage": {
            "USBMassStorage",
            "NetworkUSBMassStorage",
            "USBSDMuxDevice",
            "NetworkUSBSDMuxDevice",
            "USBSDWireDevice",
            "NetworkUSBSDWireDevice",
        },
    }
    image = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str))
    )

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.logger = logging.getLogger(f"{self}:{self.target}")

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass

    @Driver.check_active
    @step(args=['filename'])
    def write_image(self, filename=None, mode=Mode.DD, partition=None, **kwargs):
        """
        Writes the file specified by filename or if not specified by config image subkey to the
        bound USB storage root device or partition.

        Args:
            filename (str): optional, path to the image to write to bound USB storage
            mode (Mode): optional, Mode.DD or Mode.BMAPTOOL (defaults to Mode.DD)
            partition (int or None): optional, write to the specified partition or None for writing
                to root device (defaults to None)

        Kwargs (optional arguments for underlying modes):

            Mode.DD supported arguments:
            (see dd documentation on your system for more info)

                Some arguments have default values used for consistent image writing
                behavior. Set argument to `None` to reset such value.

                bs (defaults to 512 if `seek` or `skip` is present else 4M)
                status (defaults to "progress")
                conv (defaults to "fdatasync")
                oflag (defaults to "direct")
                seek (defaults to 0)
                skip (defaults to 0)
        """
        if filename is None and self.image is not None:
            filename = self.target.env.config.get_image_path(self.image)
        assert filename, "write_image requires a filename"
        mf = ManagedFile(filename, self.storage)
        mf.sync_to_resource()

        # wait for medium
        timeout = Timeout(10.0)
        while not timeout.expired:
            try:
                if self.get_size() > 0:
                    break
                time.sleep(0.5)
            except ValueError:
                # when the medium gets ready the sysfs attribute is empty for a short time span
                continue
        else:
            raise ExecutionError("Timeout while waiting for medium")

        partition = "" if partition is None else partition
        remote_path = mf.get_remote_path()
        target = f"{self.storage.path}{partition}"

        if mode == Mode.DD:
            self.logger.info('Writing %s to %s using dd.', remote_path, target)

            seek = kwargs.pop("seek", 0)
            skip = kwargs.pop("skip", 0)
            conv = kwargs.pop("conv", "fdatasync")
            bs = kwargs.pop("bs", "512" if skip or seek else "4M")
            status = kwargs.pop("status", "progress")
            oflag = kwargs.pop("oflag", "direct")

            args = [
                "dd",
                f"if={remote_path}",
                f"of={target}",
            ]
            if skip is not None:
                args.append(f"skip={skip}")
            if seek is not None:
                args.append(f"seek={seek}")
            if conv is not None:
                args.append(f"conv={conv}")
            if status is not None:
                args.append(f"status={status}")
            if oflag is not None:
                args.append(f"oflag={oflag}")
            if bs is not None:
                args.append(f"bs={bs}")

        elif mode == Mode.BMAPTOOL:

            # Try to find a block map file using the same logic that bmaptool
            # uses. Handles cases where the image is named like: <image>.bz2
            # and the block map file is <image>.bmap
            mf_bmap = None
            image_path = filename
            while True:
                bmap_path = f"{image_path}.bmap"
                if os.path.exists(bmap_path):
                    mf_bmap = ManagedFile(bmap_path, self.storage)
                    mf_bmap.sync_to_resource()
                    break

                image_path, ext = os.path.splitext(image_path)
                if not ext:
                    break

            self.logger.info('Writing %s to %s using bmaptool.', remote_path, target)
            args = [
                "bmaptool",
                "copy",
                f"{remote_path}",
                f"{target}",
            ]

            if mf_bmap is None:
                args.append("--nobmap")
            else:
                args.append(f"--bmap={mf_bmap.get_remote_path()}")
        else:
            raise ValueError

        processwrapper.check_output(
            self.storage.command_prefix + args,
            print_on_silent_log=True
        )

    @Driver.check_active
    @step(result=True)
    def get_size(self):
        args = ["cat", f"/sys/class/block/{self.storage.path[5:]}/size"]
        size = subprocess.check_output(self.storage.command_prefix + args)
        return int(size)*512


@target_factory.reg_driver
@attr.s(eq=False)
class NetworkUSBStorageDriver(USBStorageDriver):
    def __attrs_post_init__(self):
        import warnings
        warnings.warn("NetworkUSBStorageDriver is deprecated, use USBStorageDriver instead",
                      DeprecationWarning)
        super().__attrs_post_init__()
