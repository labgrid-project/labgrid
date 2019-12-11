# pylint: disable=no-member
import enum
import logging
import os
import pathlib
import subprocess
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
    WAIT_FOR_MEDIUM_TIMEOUT = 10.0 # s
    WAIT_FOR_MEDIUM_SLEEP = 0.5 # s
    PMOUNT_MEDIA_DIR = pathlib.PurePath('/media') # pmount compile-time configure option
    PUMOUNT_MAX_RETRIES = 5
    PUMOUNT_BUSY_WAIT = 3 # s

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.logger = logging.getLogger("{}:{}".format(self, self.target))

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass

    def _wait_for_medium(self, partition=None):
        timeout = Timeout(self.WAIT_FOR_MEDIUM_TIMEOUT)
        while not timeout.expired:
            if self.get_size(partition) > 0:
                break
            time.sleep(self.WAIT_FOR_MEDIUM_SLEEP)
        else:
            raise ExecutionError("Timeout while waiting for medium")

    def _pmount(self, partition):
        mount_args = ["pmount", self.storage.path + str(partition)]
        self._wait_for_medium(partition)
        processwrapper.check_output(self.storage.command_prefix + mount_args)

    def _pumount(self, partition):
        dev_path = self.storage.path + str(partition)
        for i in range(self.PUMOUNT_MAX_RETRIES):
            sync_args = ["sync", dev_path]
            processwrapper.check_output(self.storage.command_prefix + sync_args)

            umount_args = ["pumount", dev_path]
            try:
                processwrapper.check_output(self.storage.command_prefix + umount_args)
            except subprocess.CalledProcessError as e:
                if e.returncode == 5:
                    self.logger.info('umount: %s: target is busy; wait for %s s',
                                     dev_path, self.PUMOUNT_BUSY_WAIT)
                    time.sleep(self.PUMOUNT_BUSY_WAIT)
                    continue
                raise e
            break

    @Driver.check_active
    @step(args=['filenames', 'target_dir', 'partition'])
    def copy_files(self, filenames, target_dir=pathlib.PurePath("."), partition=1):
        """
        Copies the file(s) specified by filename(s) to the
        bound USB storage partition.

        Args:
            filenames (List[str]): path(s) to the file(s) to be copied to the bound USB storage
                partition.
            target_dir (str): optional, target directory to copy to (defaults to partition root
                directory)
            partition (int): optional, copy to the specified partition (defaults to first partition)
        """
        dev_path = pathlib.PurePath(self.storage.path + str(partition))
        mount_path = self.PMOUNT_MEDIA_DIR / dev_path.name

        self._pmount(partition)
        self.logger.debug('Mount %s to %s', dev_path, mount_path)

        target_path = pathlib.PurePath(mount_path) / target_dir
        try:
            for f in filenames:
                mf = ManagedFile(f, self.storage)
                mf.sync_to_resource()
                self.logger.debug("Copy %s to %s", mf.get_remote_path(), target_path)
                cp_args = ["cp", "-t", str(target_path), mf.get_remote_path()]
                processwrapper.check_output(self.storage.command_prefix + cp_args)
        finally:
            self._pumount(partition)

    @Driver.check_active
    @step(args=['filename'])
    def write_image(self, filename=None, mode=Mode.DD, partition=None, skip=0, seek=0):
        """
        Writes the file specified by filename or if not specified by config image subkey to the
        bound USB storage root device or partition.

        Args:
            filename (str): optional, path to the image to write to bound USB storage
            mode (Mode): optional, Mode.DD or Mode.BMAPTOOL (defaults to Mode.DD)
            partition (int or None): optional, write to the specified partition or None for writing
                to root device (defaults to None)
            skip (int): optional, skip n 512-sized blocks at start of input file (defaults to 0)
            seek (int): optional, skip n 512-sized blocks at start of output (defaults to 0)
        """
        if filename is None and self.image is not None:
            filename = self.target.env.config.get_image_path(self.image)
        assert filename, "write_image requires a filename"
        mf = ManagedFile(filename, self.storage)
        mf.sync_to_resource()

        self._wait_for_medium()

        partition = "" if partition is None else partition
        remote_path = mf.get_remote_path()
        target = "{}{}".format(self.storage.path, partition)

        if mode == Mode.DD:
            self.logger.info('Writing %s to %s using dd.', remote_path, target)
            block_size = '512' if skip or seek else '4M'
            args = [
                "dd",
                "if={}".format(remote_path),
                "of={}".format(target),
                "oflag=direct",
                "status=progress",
                "bs={}".format(block_size),
                "skip={}".format(skip),
                "seek={}".format(seek),
                "conv=fdatasync"
            ]
        elif mode == Mode.BMAPTOOL:
            if skip or seek:
                raise ExecutionError("bmaptool does not support skip or seek")

            # Try to find a block map file using the same logic that bmaptool
            # uses. Handles cases where the image is named like: <image>.bz2
            # and the block map file is <image>.bmap
            mf_bmap = None
            image_path = filename
            while True:
                bmap_path = "{}.bmap".format(image_path)
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
                "{}".format(remote_path),
                "{}".format(target),
            ]

            if mf_bmap is None:
                args.append("--nobmap")
            else:
                args.append("--bmap={}".format(mf_bmap.get_remote_path()))
        else:
            raise ValueError

        processwrapper.check_output(
            self.storage.command_prefix + args,
            print_on_silent_log=True
        )

    @Driver.check_active
    @step(args=['partition'], result=True)
    def get_size(self, partition=None):
        """
        Get the size of the bound USB storage root device or partition.

        Args:
            partition (int or None): optional, get size of the specified partition or None for
                getting the size of the root device (defaults to None)

        Returns:
            int: size in bytes
        """
        partition = "" if partition is None else partition
        args = ["cat", "/sys/class/block/{}{}/size".format(self.storage.path[5:], partition)]
        size = processwrapper.check_output(self.storage.command_prefix + args)
        try:
            return int(size)
        except ValueError:
            # when the medium gets ready the sysfs attribute is empty for a short time span
            return 0


@target_factory.reg_driver
@attr.s(eq=False)
class NetworkUSBStorageDriver(USBStorageDriver):
    def __attrs_post_init__(self):
        import warnings
        warnings.warn("NetworkUSBStorageDriver is deprecated, use USBStorageDriver instead",
                      DeprecationWarning)
        super().__attrs_post_init__()
