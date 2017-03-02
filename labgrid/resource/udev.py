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
    device = attr.ib(default=None, hash=False)

    def __attrs_post_init__(self):
        self.match.setdefault('SUBSYSTEM', 'usb')
        super().__attrs_post_init__()

    def filter_match(self, device):
        return True

    def try_match(self, device):
        if self.device:
            if self.device.sys_path != device.sys_path:
                return False
        else: # new device
            def match_single(dev, key, value):
                if dev.get(key) == value:
                    return True
                elif dev.attributes.get(key) == value:
                    return True
                elif getattr(dev, key, None) == value:
                    return True
                return False

            def match_ancestors(key, value):
                for ancestor in device.ancestors:
                    if match_single(ancestor, key, value):
                        return True
                return False

            for k, v in self.match.items():
                if k.startswith('@'):
                    if match_ancestors(k[1:], v):
                        continue
                elif match_single(device, k, v):
                    continue
                else:
                    return False
            if not self.filter_match(device):
                return False
        print(" found match: {}".format(self))
        if device.action in [None, 'add', 'change']:
            self.avail = True
            self.device = device
            self.update()
        else:
            self.avail = False
            self.device = None
        return True

    def update(self):
        pass

    @property
    def busnum(self):
        if self.device:
            return int(self.device.get('BUSNUM'))

    @property
    def devnum(self):
        if self.device:
            return int(self.device.get('DEVNUM'))

    def _get_usb_device(self):
        device = self.device
        if self.device and (self.device.subsystem != 'usb' or self.device.device_type != 'usb_device'):
            device = self.device.find_parent('usb', 'usb_device')
        return device

    @property
    def path(self):
        device = self._get_usb_device()
        if device:
            return str(device.sys_name)

    @property
    def vendor_id(self):
        device = self._get_usb_device()
        if device:
            return int(device.get('ID_VENDOR_ID'), 16)

    @property
    def model_id(self):
        device = self._get_usb_device()
        if device:
            return int(device.get('ID_MODEL_ID'), 16)


@target_factory.reg_resource
@attr.s
class USBSerialPort(SerialPort, USBResource):
    def __attrs_post_init__(self):
        self.match['SUBSYSTEM'] = 'tty'
        super().__attrs_post_init__()

    def update(self):
        super().update()
        self.port = self.device.device_node

@target_factory.reg_resource
@attr.s
class USBMassStorage(USBResource):
    def __attrs_post_init__(self):
        self.match['SUBSYSTEM'] = 'block'
        self.match['DEVTYPE'] = 'disk'
        self.match['@SUBSYSTEM'] = 'usb'
        super().__attrs_post_init__()

    @property
    def path(self):
        return self.device.device_node

@target_factory.reg_resource
@attr.s
class IMXUSBLoader(USBResource):
    def filter_match(self, device):
        if device.get('ID_VENDOR_ID') != "15a2":
            return False
        if device.get('ID_MODEL_ID') not in ["0054", "0061"]:
            return False
        return super().filter_match(device)


@target_factory.reg_resource
@attr.s
class MXSUSBLoader(USBResource):
    def filter_match(self, device):
        if device.get('ID_VENDOR_ID') != "066f":
            return False
        if device.get('ID_MODEL_ID') not in ["3780"]:
            return False
        return super().filter_match(device)

@target_factory.reg_resource
@attr.s
class AndroidFastboot(USBResource):
    def filter_match(self, device):
        if device.get('ID_VENDOR_ID') != "1d6b":
            return False
        if device.get('ID_MODEL_ID') != "0104":
            return False
        while device.parent and device.parent.driver != 'usb':
            device = device.parent
        return super().filter_match(device)
