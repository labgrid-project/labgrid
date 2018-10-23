# pylint: disable=unsupported-assignment-operation
from functools import partial
import logging
import os
import warnings
import attr
import pyudev

from ..factory import target_factory
from .common import ManagedResource, ResourceManager
from .base import SerialPort, EthernetInterface


@attr.s(cmp=False)
class UdevManager(ResourceManager):
    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.log = logging.getLogger('UdevManager')
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
            self.log.debug("%s: %s", device.action, device)
            for resource in self.resources:
                self.log.debug(" %s", resource)
                if resource.try_match(device):
                    break


@attr.s(cmp=False)
class USBResource(ManagedResource):
    manager_cls = UdevManager

    match = attr.ib(default={}, validator=attr.validators.instance_of(dict), hash=False)
    device = attr.ib(default=None, hash=False)

    def __attrs_post_init__(self):
        self.timeout = 5.0
        self.log = logging.getLogger('USBResource')
        self.match.setdefault('SUBSYSTEM', 'usb')
        super().__attrs_post_init__()

    def filter_match(self, device):  # pylint: disable=unused-argument,no-self-use
        return True

    def try_match(self, device):
        if self.device:
            if self.device.sys_path != device.sys_path:
                return False
        else: # new device
            def match_single(dev, key, value):
                if dev.properties.get(key) == value:
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
        self.log.debug(" found match: %s", self)
        if device.action in [None, 'add']:
            if self.avail:
                warnings.warn("udev device {} is already available".format(device))
            self.avail = True
            self.device = device
        elif device.action in ['change', 'move']:
            self.device = device
        elif device.action in ['unbind', 'remove']:
            self.avail = False
            self.device = None
        self.update()
        return True

    def update(self):
        pass

    @property
    def busnum(self):
        device = self._get_usb_device()
        if device:
            return int(device.properties.get('BUSNUM'))

        return None

    @property
    def devnum(self):
        device = self._get_usb_device()
        if device:
            return int(device.properties.get('DEVNUM'))

        return None

    def _get_usb_device(self):
        device = self.device
        if self.device and (self.device.subsystem != 'usb'
                            or self.device.device_type != 'usb_device'):
            device = self.device.find_parent('usb', 'usb_device')
        return device

    @property
    def path(self):
        device = self._get_usb_device()
        if device:
            return str(device.sys_name)

        return None

    @property
    def vendor_id(self):
        device = self._get_usb_device()
        if device:
            return int(device.properties.get('ID_VENDOR_ID'), 16)

        return None

    @property
    def model_id(self):
        device = self._get_usb_device()
        if device:
            return int(device.properties.get('ID_MODEL_ID'), 16)

        return None

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

        return None


@target_factory.reg_resource
@attr.s(cmp=False)
class USBSerialPort(USBResource, SerialPort):
    def __attrs_post_init__(self):
        self.match['SUBSYSTEM'] = 'tty'
        if self.port:
            warnings.warn(
                "USBSerialPort: The port attribute will be overwritten by udev.\n"
                "Please use udev matching as described in http://labgrid.readthedocs.io/en/latest/getting_started.html#udev-matching"
            )
        super().__attrs_post_init__()

    def update(self):
        super().update()
        if self.device:
            self.port = self.device.device_node
        else:
            self.port = None

@target_factory.reg_resource
@attr.s(cmp=False)
class USBMassStorage(USBResource):
    def __attrs_post_init__(self):
        self.match['SUBSYSTEM'] = 'block'
        self.match['DEVTYPE'] = 'disk'
        self.match['@SUBSYSTEM'] = 'usb'
        super().__attrs_post_init__()

    @property
    def path(self):
        if self.device:
            return self.device.device_node

        return None

@target_factory.reg_resource
@attr.s(cmp=False)
class IMXUSBLoader(USBResource):
    def filter_match(self, device):
        match = (device.properties.get('ID_VENDOR_ID'), device.properties.get('ID_MODEL_ID'))

        if match not in [("15a2", "0054"), ("15a2", "0061"),
                         ("15a2", "0063"), ("15a2", "0071"),
                         ("15a2", "007d"), ("15a2", "0076"),
                         ("15a2", "0080"), ("15a2", "003a"),
                         ("1fc9", "0128"), ("1fc9", "0126")]:
            return False

        return super().filter_match(device)


@target_factory.reg_resource
@attr.s(cmp=False)
class MXSUSBLoader(USBResource):
    def filter_match(self, device):
        match = (device.properties.get('ID_VENDOR_ID'), device.properties.get('ID_MODEL_ID'))

        if match not in [("066f", "3780"), ("15a2", "004f")]:
            return False

        return super().filter_match(device)

@target_factory.reg_resource
@attr.s(cmp=False)
class AndroidFastboot(USBResource):
    usb_vendor_id = attr.ib(default='1d6b', validator=attr.validators.instance_of(str))
    usb_product_id = attr.ib(default='0104', validator=attr.validators.instance_of(str))
    def filter_match(self, device):
        if device.properties.get('ID_VENDOR_ID') != self.usb_vendor_id:
            return False
        if device.properties.get('ID_MODEL_ID') != self.usb_product_id:
            return False
        return super().filter_match(device)

@target_factory.reg_resource
@attr.s(cmp=False)
class USBEthernetInterface(USBResource, EthernetInterface):
    def __attrs_post_init__(self):
        self.match['SUBSYSTEM'] = 'net'
        self.match['@SUBSYSTEM'] = 'usb'
        super().__attrs_post_init__()

    def update(self):
        super().update()
        if self.device:
            self.ifname = self.device.properties.get('INTERFACE')
        else:
            self.ifname = None

    @property
    def if_state(self):
        value = self.read_attr('operstate')
        if value is not None:
            value = value.decode('ascii')
        return value

@target_factory.reg_resource
@attr.s(cmp=False)
class AlteraUSBBlaster(USBResource):
    def filter_match(self, device):
        if device.properties.get('ID_VENDOR_ID') != "09fb":
            return False
        if device.properties.get('ID_MODEL_ID') not in ["6010", "6810"]:
            return False
        return super().filter_match(device)

@target_factory.reg_resource
@attr.s(cmp=False)
class SigrokUSBDevice(USBResource):
    """The SigrokUSBDevice describes an attached sigrok device with driver and
    channel mapping, it is identified via usb using udev

    Args:
        driver (str): driver to use with sigrok
        channels (str): a sigrok channel mapping as desribed in the sigrok-cli man page
    """
    driver = attr.ib(default=None, validator=attr.validators.instance_of(str))
    channels = attr.ib(default=None, validator=attr.validators.instance_of(str))
    def __attrs_post_init__(self):
        self.match['@SUBSYSTEM'] = 'usb'
        super().__attrs_post_init__()

@target_factory.reg_resource
@attr.s(cmp=False)
class USBSDMuxDevice(USBResource):
    """The USBSDMuxDevice describes an attached USBSDMux device,
    it is identified via USB using udev
    """
    def __attrs_post_init__(self):
        self.match['ID_VENDOR_ID'] = '0424'
        self.match['ID_MODEL_ID'] = '4041'
        self.control_path = None
        self.disk_path = None
        super().__attrs_post_init__()

    def update(self):
        super().update()
        if not self.device:
            self.control_path = None
            self.path = None
        for child in self.device.children:
            if child.subsystem == 'block':
                self.disk_path = child.device_node
            elif child.subsystem == 'scsi_generic':
                self.control_path = child.device_node

    @property
    def path(self):
        return self.disk_path

@target_factory.reg_resource
@attr.s(cmp=False)
class USBPowerPort(USBResource):
    """The USBPowerPort describes a single port on an USB hub which supports
    power control.

    Args:
        index (int): index of the downstream port on the USB hub
    """
    index = attr.ib(default=None, validator=attr.validators.instance_of(int))
    def __attrs_post_init__(self):
        self.match['DEVTYPE'] = 'usb_interface'
        self.match['DRIVER'] = 'hub'
        super().__attrs_post_init__()

@target_factory.reg_resource
@attr.s(cmp=False)
class USBVideo(USBResource):
    def __attrs_post_init__(self):
        self.match['SUBSYSTEM'] = 'video4linux'
        self.match['@SUBSYSTEM'] = 'usb'
        super().__attrs_post_init__()

    @property
    def path(self):
        if self.device:
            return self.device.device_node

        return None

@target_factory.reg_resource
@attr.s(cmp=False)
class USBTMC(USBResource):
    def __attrs_post_init__(self):
        self.match['SUBSYSTEM'] = 'usbmisc'
        self.match['@DRIVER'] = 'usbtmc'
        self.match['@SUBSYSTEM'] = 'usb'
        super().__attrs_post_init__()

    @property
    def path(self):
        if self.device:
            return self.device.device_node

        return None
