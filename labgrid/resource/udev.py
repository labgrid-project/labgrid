from functools import partial

import attr
import pyudev

from ..factory import target_factory
from .common import ManagedResource, ResourceManager
from .base import SerialPort


@attr.s
class UdevManager(ResourceManager):
    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._context = pyudev.Context()
        self._monitor = pyudev.Monitor.from_netlink(self._context)
        self._monitor.start()

    def on_resource_added(self, resource):
        devices = self._context.list_devices()
        devices.match_subsystem(resource.match['SUBSYSTEM'])
        for device in devices:
            if resource.try_match(device):
                break

    def poll(self):
        for device in iter(partial(self._monitor.poll, 0), None):
            print("{0.action}: {0}".format(device))
            for resource in self.resources:
                print(" {}".format(resource))
                if resource.try_match(device):
                    break


@attr.s
class USBResource(ManagedResource):
    manager_cls = UdevManager

    match = attr.ib(validator=attr.validators.instance_of(dict), hash=False)
    _device = attr.ib(default=None, hash=False)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    def try_match(self, device):
        for k, v in self.match.items():
            if device.get(k) != v:
                return False
            print("  {}={}".format(k, v))
        print(" found match: {}".format(self))
        self.device = device
        return True

    def on_device_set(self):
        raise NotImplementedError()

    @property
    def device(self):
        return self._device

    @device.setter
    def device(self, value):
        self._device = value
        self.on_device_set()


@target_factory.reg_resource
@attr.s
class USBSerialPort(SerialPort, USBResource):
    def __attrs_post_init__(self):
        self.match['SUBSYSTEM'] = 'tty'
        super().__attrs_post_init__()

    def on_device_set(self):
        self.port = self.device.device_node
        self.avail = True
