"""
This module implements mounting file systems via communication with udisksd.
"""
import logging
import time

import gi
gi.require_version('UDisks', '2.0')
from gi.repository import GLib, UDisks

class UDisks2Device:
    UNMOUNT_MAX_RETRIES = 5
    UNMOUNT_BUSY_WAIT = 3 # s

    def __init__(self, devpath):
        self._logger = logging.getLogger("Device: ")
        self.devpath = devpath
        client = UDisks.Client.new_sync(None)

        manager = client.get_object_manager()
        for obj in manager.get_objects():
            block = obj.get_block()
            if not block:
                continue

            device_path = block.get_cached_property("Device").get_bytestring().decode('utf-8')
            if device_path == devpath:
                self.fs = obj.get_filesystem()
                if self.fs is None:
                    raise ValueError(f"no filesystem found on {devpath}")

                return

        raise ValueError(f"No udisks2 device found for {devpath}")

    def mount(self, readonly=False):
        opts = GLib.Variant('a{sv}', {'options': GLib.Variant('s', 'ro' if readonly else 'rw')})

        try:
            mountpoint = self.fs.call_mount_sync(opts, None)
        except GLib.GError as err:
            if not err.matches(UDisks.error_quark(), UDisks.Error.ALREADY_MOUNTED):
                raise err

            self._logger.warning('Unmounting lazily and remounting %s...', self.devpath)
            self._unmount_lazy()

            mountpoint = self.fs.call_mount_sync(opts, None)

        return mountpoint

    def _unmount_lazy(self):
        opts = GLib.Variant('a{sv}', {'force': GLib.Variant('b', True)})

        try:
            self.fs.call_unmount_sync(opts, None)
        except GLib.GError as err:
            if not err.matches(UDisks.error_quark(), UDisks.Error.NOT_MOUNTED):
                raise err

    def _unmount(self):
        opts = GLib.Variant('a{sv}', {'force': GLib.Variant('b', False)})

        for _ in range(self.UNMOUNT_MAX_RETRIES):
            try:
                self.fs.call_unmount_sync(opts, None)
                return
            except GLib.GError as err:
                if not err.matches(UDisks.error_quark(), UDisks.Error.DEVICE_BUSY):
                    raise err

                self._logger.warning('waiting %s s for busy %s',
                                     self.UNMOUNT_BUSY_WAIT, self.devpath)
                time.sleep(self.UNMOUNT_BUSY_WAIT)

        raise TimeoutError("Timeout waiting for device to become non-busy")

    def unmount(self, lazy=False):
        if lazy:
            self._unmount_lazy()
        else:
            self._unmount()

_devs = {}

def _get_udisks2_dev(devpath):
    if devpath not in _devs:
        _devs[devpath] = UDisks2Device(devpath=devpath)
    return _devs[devpath]

def handle_mount(devpath):
    dev = _get_udisks2_dev(devpath)
    return dev.mount()

def handle_unmount(devpath, lazy=False):
    dev = _get_udisks2_dev(devpath)
    return dev.unmount(lazy=lazy)

methods = {
    'mount': handle_mount,
    'unmount': handle_unmount,
}
