"""
This module implements formatting and mounting file systems via udisksd.
"""

import logging
import time

import gi

gi.require_version("UDisks", "2.0")
from gi.repository import GLib, UDisks


class UDisks2Device:
    UNMOUNT_MAX_RETRIES = 5
    UNMOUNT_BUSY_WAIT = 3  # s

    def __init__(self, devpath):
        self._logger = logging.getLogger("Device: ")
        self.devpath = devpath
        self.fs = None

    def _setup(self):
        """Try to find the devpath

        Raises:
            ValueError: no udisks2 device or no filesystem found on devpath
        """
        device = _find_udisks2_object(self.devpath)
        if device is None:
            raise ValueError(f"No udisks2 device found for {self.devpath}")
        self.fs = device.get_filesystem()
        if self.fs is None:
            raise ValueError(f"no filesystem found on {self.devpath}")

    def mount(self, readonly=False, retries=0):
        opts = GLib.Variant("a{sv}", {"options": GLib.Variant("s", "ro" if readonly else "rw")})

        try:
            mountpoint = self.fs.call_mount_sync(opts, None)
        except GLib.GError as err:
            if not err.matches(UDisks.error_quark(), UDisks.Error.ALREADY_MOUNTED):
                raise err

            self._logger.warning("Unmounting lazily and remounting %s...", self.devpath)
            self._unmount_lazy()

            mountpoint = self.fs.call_mount_sync(opts, None)

        return mountpoint

    def _unmount_lazy(self):
        opts = GLib.Variant("a{sv}", {"force": GLib.Variant("b", True)})

        try:
            self.fs.call_unmount_sync(opts, None)
        except GLib.GError as err:
            if not err.matches(UDisks.error_quark(), UDisks.Error.NOT_MOUNTED):
                raise err

    def _unmount(self):
        opts = GLib.Variant("a{sv}", {"force": GLib.Variant("b", False)})

        for _ in range(self.UNMOUNT_MAX_RETRIES):
            try:
                self.fs.call_unmount_sync(opts, None)
                return
            except GLib.GError as err:
                if not err.matches(UDisks.error_quark(), UDisks.Error.DEVICE_BUSY):
                    raise err

                self._logger.warning("waiting %s s for busy %s", self.UNMOUNT_BUSY_WAIT, self.devpath)
                time.sleep(self.UNMOUNT_BUSY_WAIT)

        raise TimeoutError("Timeout waiting for device to become non-busy")

    def unmount(self, lazy=False):
        if lazy:
            self._unmount_lazy()
        else:
            self._unmount()


_devs = {}


def _get_udisks2_dev(devpath, retries):
    """Try to get the udisks2 device

    Args:
        devpath (str): Device name
        retries (int): Number of retries to allow

    Raises:
        ValueError: Failed to obtain the device (e.g. does not exist)
    """
    if devpath not in _devs:
        dev = UDisks2Device(devpath=devpath)
        while True:
            try:
                dev._setup()
                break
            except ValueError as exc:
                if "No udisks2 device" not in str(exc) or not retries:
                    raise
                retries -= 1
            dev._logger.warning("udisks2: Retrying %s...", devpath)
            time.sleep(1)

        # Success, so record the new device
        _devs[devpath] = dev
    return _devs[devpath]


def handle_mount(devpath, retries=0):
    dev = _get_udisks2_dev(devpath, retries)
    return dev.mount()


def handle_unmount(devpath, lazy=False):
    dev = _get_udisks2_dev(devpath, 0)
    return dev.unmount(lazy=lazy)


def _find_udisks2_object(devpath):
    client = UDisks.Client.new_sync(None)
    manager = client.get_object_manager()
    for obj in manager.get_objects():
        block = obj.get_block()
        if block is None:
            continue
        device_path = block.get_cached_property("Device").get_bytestring().decode("utf-8")
        if device_path == devpath:
            return obj
    return None


def handle_create_partition_table(devpath, table_type="dos"):
    """Create a partition table, erasing existing partition data."""
    device = _find_udisks2_object(devpath)
    if device is None:
        raise ValueError(f"No udisks2 device found for {devpath}")
    # Formatting invalidates cached filesystem proxies, including on failure.
    _devs.clear()
    device.get_block().call_format_sync(table_type, GLib.Variant("a{sv}", {}), None)


def handle_has_partition_table(devpath):
    device = _find_udisks2_object(devpath)
    return device is not None and device.get_partition_table() is not None


def handle_create_partition_and_format(
    devpath, filesystem="vfat", label="", offset=1048576, size=0,
):
    """Create and format a partition, returning its end offset in bytes.

    Args:
        devpath (str): Block device path.
        filesystem (str): Filesystem type, such as ``vfat`` or ``ext4``.
        label (str): Filesystem label.
        offset (int): Partition start offset in bytes.
        size (int): Partition size in bytes, or 0 to use the remaining space.
    """
    device = _find_udisks2_object(devpath)
    if device is None:
        raise ValueError(f"No udisks2 device found for {devpath}")
    partition_table = device.get_partition_table()
    if partition_table is None:
        raise ValueError(f"No partition table found on {devpath}")

    options = {}
    if partition_table.get_cached_property("Type").get_string() == "dos":
        options["partition-type"] = GLib.Variant("s", "primary")
    partition_options = GLib.Variant("a{sv}", options)
    format_options = {"label": GLib.Variant("s", label)}
    if filesystem == "vfat":
        format_options["mkfs-args"] = GLib.Variant("as", ["-F", "32"])
    else:
        # Without this, the ext4 root is owned by root and the invoking user
        # cannot write to the mounted filesystem.
        format_options["take-ownership"] = GLib.Variant("b", True)
    path = partition_table.call_create_partition_and_format_sync(
        offset,
        size,
        "",
        "",
        partition_options,
        filesystem,
        GLib.Variant("a{sv}", format_options),
        None,
    )
    _devs.clear()
    client = UDisks.Client.new_sync(None)
    partition = client.get_object(path).get_partition()
    return (
        partition.get_cached_property("Offset").get_uint64()
        + partition.get_cached_property("Size").get_uint64()
    )


methods = {
    "create_partition_table": handle_create_partition_table,
    "has_partition_table": handle_has_partition_table,
    "create_partition_and_format": handle_create_partition_and_format,
    "mount": handle_mount,
    "unmount": handle_unmount,
}
