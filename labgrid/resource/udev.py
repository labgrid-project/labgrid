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
        self.match.setdefault('SUBSYSTEM', 'usb')
        super().__attrs_post_init__()

    def try_match(self, device):
        def match_ancestors(key, value):
            for ancestor in device.ancestors:
                if ancestor.get(key) == value:
                    return True
            return False
        for k, v in self.match.items():
            if k.startswith('@') and match_ancestors(k[1:], v):
                continue
            elif device.get(k) == v:
                continue
            else:
                return False
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

@target_factory.reg_resource
@attr.s
class IMXUSBLoader(USBResource):
    def try_match(self, device):
        if device.get('ID_VENDOR_ID') != "15a2":
            return False
        if device.get('ID_MODEL_ID') not in ["0054", "0061"]:
            return False
        return super().try_match(device)

    def on_device_set(self):
        self.avail = True

    @property
    def busnum(self):
        return int(self.device.get_property('BUSNUM'))

    def devnum(self):
        return int(self.device.get_property('DEVNUM'))

@target_factory.reg_resource
@attr.s
class MXSUSBLoader(USBResource):
    def try_match(self, device):
        if device.get('ID_VENDOR_ID') != "066f":
            return False
        if device.get('ID_MODEL_ID') not in ["3780"]:
            return False
        print('foo', device)

        return super().try_match(device)

    def on_device_set(self):
        self.avail = True

    @property
    def busnum(self):
        return int(self.device.get('BUSNUM'))

    @property
    def devnum(self):
        return int(self.device.get('DEVNUM'))

@target_factory.reg_resource
@attr.s
class AndroidFastboot(USBResource):
    def try_match(self, device):
        if device.get('ID_VENDOR_ID') != "1d6b":
            return False
        if device.get('ID_VENDOR_ID') != "0104":
            return False
        while device.parent and device.parent.driver != 'usb':
            device = device.parent
        return super().try_match(device)

    def on_device_set(self):
        self.avail = True

    @property
    def busnum(self):
        return int(self.device.get('BUSNUM'))

    @property
    def devnum(self):
        return int(self.device.get('DEVNUM'))
