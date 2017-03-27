from functools import partial

import attr
import os
import pyudev
import warnings

from ..factory import target_factory
from .common import ManagedResource, ResourceManager
from .base import SerialPort, EthernetInterface


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
        self.timeout = 5.0
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
                    if not match_ancestors(k[1:], v):
                        return False
                else:
                    if not match_single(device, k, v):
                        return False

            if not self.filter_match(device):
                return False
        print(" found match: {}".format(self))
        if device.action in [None, 'add']:
            if self.avail:
                warnings.warn("udev device {} is already available".format(device))
            self.avail = True
            self.device = device
        elif device.action in ['change', 'move']:
            self.device = device
        else:
            self.avail = False
            self.device = None
        self.update()
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

    def read_attr(self, attribute):
        """read uncached attribute value from sysfs

        pyudev currently supports only cached access to attributes, so we read
        directly from sysfs.
        """
        # FIXME update pyudev to support udev_device_set_sysattr_value(dev,
        # attr, None) to clear the cache
        if self.device:
            with open(os.path.join(self.device.sys_path, attribute), 'rb') as f:
                return f.read().rstrip(b'\n') # drop trailing newlines


@target_factory.reg_resource
@attr.s
class USBSerialPort(SerialPort, USBResource):
    def __attrs_post_init__(self):
        self.match['SUBSYSTEM'] = 'tty'
        super().__attrs_post_init__()

    def update(self):
        super().update()
        if self.device:
            self.port = self.device.device_node
        else:
            self.port = None

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
        return super().filter_match(device)

@target_factory.reg_resource
@attr.s
class USBEthernetInterface(EthernetInterface, USBResource):
    def __attrs_post_init__(self):
        self.match['SUBSYSTEM'] = 'net'
        self.match['@SUBSYSTEM'] = 'usb'
        super().__attrs_post_init__()

    def update(self):
        super().update()
        if self.device:
            self.ifname = self.device.get('INTERFACE')
        else:
            self.ifname = None

    @property
    def if_state(self):
        value = self.read_attr('operstate')
        if value is not None:
            value = value.decode('ascii')
        return value

@target_factory.reg_resource
@attr.s
class AlteraUSBBlaster(USBResource):
    def filter_match(self, device):
        if device.get('ID_VENDOR_ID') != "09fb":
            return False
        if device.get('ID_MODEL_ID') != "6810":
            return False
        return super().filter_match(device)
