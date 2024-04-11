import enum
import os
import pathlib
import time
import subprocess

import attr

from ..factory import target_factory
from ..resource.remote import RemoteUSBResource
from ..step import step
from ..util.managedfile import ManagedFile
from .common import Driver
from ..driver.exception import ExecutionError

from ..util.helper import processwrapper
from ..util.agentwrapper import AgentWrapper
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
    MOUNT_RETRIES = 5

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.wrapper = None
        self.proxy = None

    def _start_wrapper(self):
        if self.wrapper:
            return
        host = self.storage.host if isinstance(self.storage, RemoteUSBResource) else None
        self.wrapper = AgentWrapper(host)
        self.proxy = self.wrapper.load('udisks2')

    def on_activate(self):
        pass

    def on_deactivate(self):
        if self.wrapper:
            self.wrapper.close()
        self.wrapper = None
        self.proxy = None

    @Driver.check_active
    @step(args=['sources', 'target', 'partition', 'target_is_directory'])
    def write_files(self, sources, target, partition, target_is_directory=True):
        """
        Write the file(s) specified by filename(s) to the
        bound USB storage partition.

        Args:
            sources (List[str]): path(s) to the file(s) to be copied to the bound USB storage
                partition.
            target (PurePath): target directory or file to copy to
            partition (int): mount the specified partition or None to mount the whole disk
            target_is_directory (bool): Whether target is a directory

        Raises:
            Exception if anything goes wrong
        """
        self._wait_for_medium(partition)

        self._start_wrapper()

        self.devpath = self._get_devpath(partition)
        mount_path = self.proxy.mount(self.devpath, self.MOUNT_RETRIES)

        try:
            # (pathlib.PurePath(...) / "/") == "/", so we turn absolute paths into relative
            # paths with respect to the mount point here
            target_rel = target.relative_to(target.root) if target.root is not None else target
            target_path = str(pathlib.PurePath(mount_path) / target_rel)

            copied_sources = []

            for f in sources:
                mf = ManagedFile(f, self.storage)
                mf.sync_to_resource()
                copied_sources.append(mf.get_remote_path())

            if target_is_directory:
                args = ["cp", "-t", target_path] + copied_sources
            else:
                if len(sources) != 1:
                    raise ValueError("single source argument required when target_is_directory=False")

                args = ["cp", "-T", copied_sources[0], target_path]

            processwrapper.check_output(self.storage.command_prefix + args)
            self.proxy.unmount(self.devpath)
        except:
            # We are going to die with an exception anyway, so no point in waiting
            # to make sure everything has been written before continuing
            self.proxy.unmount(self.devpath, lazy=True)
            raise

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

        self._wait_for_medium(partition)

        target = self._get_devpath(partition)
        remote_path = mf.get_remote_path()

        if mode == Mode.DD:
            self.logger.info('Writing %s to %s using dd.', remote_path, target)
            block_size = '512' if skip or seek else '4M'
            args = [
                "dd",
                f"if={remote_path}",
                f"of={target}",
                "oflag=direct",
                "status=progress",
                f"bs={block_size}",
                f"skip={skip}",
                f"seek={seek}",
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

    def _get_devpath(self, partition):
        partition = "" if partition is None else partition
        # simple concatenation is sufficient for USB mass storage
        return f"{self.storage.path}{partition}"

    @Driver.check_active
    def _wait_for_medium(self, partition):
        timeout = Timeout(self.WAIT_FOR_MEDIUM_TIMEOUT)
        while not timeout.expired:
            if self.get_size(partition) > 0:
                break
            time.sleep(self.WAIT_FOR_MEDIUM_SLEEP)
        else:
            raise ExecutionError("Timeout while waiting for medium")

    @Driver.check_active
    @step(args=['partition'], result=True)
    def get_size(self, partition=None):
        """
        Get the size of the bound USB storage root device or partition.

        Args:
            partition (int or None): optional, get size of the specified partition or None for
                getting the size of the root device (defaults to None)

        Returns:
            int: size in bytes, or 0 if the partition is not found
        """
        args = ["cat", f"/sys/class/block/{self._get_devpath(partition)[5:]}/size"]
        try:
            size = subprocess.check_output(self.storage.command_prefix + args)
        except subprocess.CalledProcessError:
            # while the medium is getting ready, the file does not yet exist
            return 0
        try:
            return int(size) * 512
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
