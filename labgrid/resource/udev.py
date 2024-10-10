import os
import queue
import warnings
from collections import OrderedDict
from importlib import import_module

import attr

from ..factory import target_factory
from .common import ManagedResource, ResourceManager
from .base import SerialPort, NetworkInterface
from ..util import Timeout


@attr.s(eq=False)
class UdevManager(ResourceManager):
    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.queue = queue.Queue()

        self._pyudev = import_module('pyudev')
        self._context = self._pyudev.Context()
        self._monitor = self._pyudev.Monitor.from_netlink(self._context)
        self._observer = self._pyudev.MonitorObserver(self._monitor,
                                                callback=self._insert_into_queue)
        self._observer.start()

    def on_resource_added(self, resource):
        devices = self._context.list_devices()
        devices.match_subsystem(resource.match['SUBSYSTEM'])
        for device in devices:
            if resource.try_match(device):
                self.logger.debug(" matched successfully against %s", resource.device)

    def _insert_into_queue(self, device):
        self.queue.put(device)

    def poll(self):
        timeout = Timeout(0.1)
        while not timeout.expired:
            try:
                device = self.queue.get(False)
            except queue.Empty:
                break
            self.logger.debug("%s: %s", device.action, device)
            for resource in self.resources:
                if resource.try_match(device):
                    self.logger.debug(" matched successfully")

@attr.s(eq=False)
class USBResource(ManagedResource):
    manager_cls = UdevManager

    match = attr.ib(factory=dict, validator=attr.validators.instance_of(dict), hash=False)
    device = attr.ib(default=None, hash=False)
    suggest = attr.ib(default=False, hash=False, repr=False)

    def __attrs_post_init__(self):
        self.timeout = 5.0
        self.match.setdefault('SUBSYSTEM', 'usb')
        super().__attrs_post_init__()

    def filter_match(self, device):  # pylint: disable=unused-argument
        return True

    def suggest_match(self, device):
        meta = OrderedDict()
        suggestions = []

        if self.device.device_node:
            meta['device node'] = self.device.device_node
        if list(self.device.tags):
            meta['udev tags'] = ', '.join(self.device.tags)
        if self.device.properties.get('ID_VENDOR'):
            meta['vendor'] = self.device.properties.get('ID_VENDOR')
        if self.device.properties.get('ID_VENDOR_FROM_DATABASE'):
            meta['vendor (DB)'] = self.device.properties.get('ID_VENDOR_FROM_DATABASE')
        if self.device.properties.get('ID_MODEL'):
            meta['model'] = self.device.properties.get('ID_MODEL')
        if self.device.properties.get('ID_MODEL_FROM_DATABASE'):
            meta['model (DB)'] = self.device.properties.get('ID_MODEL_FROM_DATABASE')
        if self.device.properties.get('ID_REVISION'):
            meta['revision'] = self.device.properties.get('ID_REVISION')

        path = self.device.properties.get('ID_PATH')
        if path:
            suggestions.append({'ID_PATH': path})
        elif self.match.get('@SUBSYSTEM', None) == 'usb':
            path = self._get_usb_device().properties.get('ID_PATH')
            if path:
                suggestions.append({'@ID_PATH': path})

        serial = self.device.properties.get('ID_SERIAL_SHORT')
        interface_num = self.device.properties.get('ID_USB_INTERFACE_NUM')
        if serial:
            if interface_num is not None:
                suggestions.append({'ID_SERIAL_SHORT': serial,
                                    'ID_USB_INTERFACE_NUM': interface_num})
            else:
                suggestions.append({'ID_SERIAL_SHORT': serial})
        elif self.match.get('@SUBSYSTEM', None) == 'usb':
            serial = self._get_usb_device().properties.get('ID_SERIAL_SHORT')
            interface_num = self._get_usb_device().properties.get('ID_USB_INTERFACE_NUM')
            if serial:
                if interface_num is not None:
                    suggestions.append({'@ID_SERIAL_SHORT': serial,
                                        '@ID_USB_INTERFACE_NUM': interface_num})
                else:
                    suggestions.append({'@ID_SERIAL_SHORT': serial})

        return meta, suggestions

    def try_match(self, device):
        if self.device is None:  # new device
            def match_single(dev, key, value):
                if dev.properties.get(key) == value:
                    return True
                if dev.attributes.get(key) and dev.attributes.asstring(key) == value:
                    return True
                if getattr(dev, key, None) == value:
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
        else:  # update
            if self.device.sys_path != device.sys_path:
                return False

        self.logger.debug(" found match: %s", self)

        if self.suggest and device.action in [None, 'add']:
            self.device = device
            self.suggest(self, *self.suggest_match(device))
            self.device = None
            return False

        if device.action in [None, 'add']:
            if self.avail:
                warnings.warn(f"udev device {device} is already available")
            self.device = device
        elif device.action in ['change', 'move']:
            self.device = device
        elif device.action in ['unbind', 'remove']:
            self.device = None

        self.avail = self.device is not None
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
        if self.device is not None and (self.device.subsystem != 'usb'
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
        if self.device is not None:
            with open(os.path.join(self.device.sys_path, attribute), 'rb') as f:
                return f.read().rstrip(b'\n') # drop trailing newlines

        return None


@target_factory.reg_resource
@attr.s(eq=False)
class USBSerialPort(USBResource, SerialPort):
    def __attrs_post_init__(self):
        self.match['SUBSYSTEM'] = 'tty'
        self.match['@SUBSYSTEM'] = 'usb'
        if self.port:
            warnings.warn(
                "USBSerialPort: The port attribute will be overwritten by udev.\n"
                "Please use udev matching as described in http://labgrid.readthedocs.io/en/latest/configuration.html#udev-matching"  # pylint: disable=line-too-long
            )
        super().__attrs_post_init__()

    def update(self):
        super().update()
        if self.device is not None:
            self.port = self.device.device_node
        else:
            self.port = None

@target_factory.reg_resource
@attr.s(eq=False)
class USBMassStorage(USBResource):
    def __attrs_post_init__(self):
        self.match['SUBSYSTEM'] = 'block'
        self.match['DEVTYPE'] = 'disk'
        self.match['@SUBSYSTEM'] = 'usb'
        super().__attrs_post_init__()

    # Overwrite the avail attribute with our internal property
    @property
    def avail(self):
        return self.path is not None

    # Forbid the USBResource super class to set the avail property
    @avail.setter
    def avail(self, prop):
        pass

    @property
    def path(self):
        if self.device is not None:
            return self.device.device_node

        return None

@target_factory.reg_resource
@attr.s(eq=False)
class IMXUSBLoader(USBResource):
    def filter_match(self, device):
        match = (device.properties.get('ID_VENDOR_ID'), device.properties.get('ID_MODEL_ID'))

        if match not in [("15a2", "0054"), ("15a2", "0061"),
                         ("15a2", "0063"), ("15a2", "0071"),
                         ("15a2", "007d"), ("15a2", "0076"),
                         ("15a2", "0080"), ("15a2", "003a"),
                         ("1fc9", "0128"), ("1fc9", "0126"),
                         ("1fc9", "012b"), ("1fc9", "0134"),
                         ("1fc9", "013e"), ("1fc9", "0146"),
                         ("1fc9", "014e"),
                         ("1b67", "4fff"), ("0525", "b4a4"), # SPL
                         ("3016", "1001"),
                         ]:
            return False

        return super().filter_match(device)

@target_factory.reg_resource
@attr.s(eq=False)
class RKUSBLoader(USBResource):
    def filter_match(self, device):
        match = (device.properties.get('ID_VENDOR_ID'), device.properties.get('ID_MODEL_ID'))

        if match not in [("2207", "110a")]:
            return False

        return super().filter_match(device)

@target_factory.reg_resource
@attr.s(eq=False)
class MXSUSBLoader(USBResource):
    def filter_match(self, device):
        match = (device.properties.get('ID_VENDOR_ID'), device.properties.get('ID_MODEL_ID'))

        if match not in [("066f", "3780"), ("15a2", "004f")]:
            return False

        return super().filter_match(device)

@target_factory.reg_resource
@attr.s(eq=False)
class AndroidUSBFastboot(USBResource):
    usb_vendor_id = attr.ib(default='1d6b', validator=attr.validators.instance_of(str))
    usb_product_id = attr.ib(default='0104', validator=attr.validators.instance_of(str))
    def filter_match(self, device):
        if device.properties.get("adb_user") == "yes":
            return True
        if device.properties.get('ID_VENDOR_ID') != self.usb_vendor_id:
            return False
        if device.properties.get('ID_MODEL_ID') != self.usb_product_id:
            return False
        return super().filter_match(device)

@target_factory.reg_resource
@attr.s(eq=False)
class AndroidFastboot(AndroidUSBFastboot):
    def __attrs_post_init__(self):
        warnings.warn("AndroidFastboot is deprecated, use AndroidUSBFastboot instead",
                      DeprecationWarning)
        super().__attrs_post_init__()

@target_factory.reg_resource
@attr.s(eq=False)
class DFUDevice(USBResource):
    def filter_match(self, device):
        if ':fe0102:' not in device.properties.get('ID_USB_INTERFACES', ''):
            return False

        return super().filter_match(device)

@target_factory.reg_resource
@attr.s(eq=False)
class USBNetworkInterface(USBResource, NetworkInterface):
    def __attrs_post_init__(self):
        self.match['SUBSYSTEM'] = 'net'
        self.match['@SUBSYSTEM'] = 'usb'
        if self.ifname:
            warnings.warn(
                "USBNetworkInterface: The ifname attribute will be overwritten by udev.\n"
                "Please use udev matching as described in http://labgrid.readthedocs.io/en/latest/configuration.html#udev-matching"  # pylint: disable=line-too-long
            )
        super().__attrs_post_init__()

    def update(self):
        super().update()
        if self.device is not None:
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
@attr.s(eq=False)
class AlteraUSBBlaster(USBResource):
    def filter_match(self, device):
        if device.properties.get('ID_VENDOR_ID') != "09fb":
            return False
        if device.properties.get('ID_MODEL_ID') not in ["6010", "6810"]:
            return False
        return super().filter_match(device)

@target_factory.reg_resource
@attr.s(eq=False)
class SigrokUSBDevice(USBResource):
    """The SigrokUSBDevice describes an attached sigrok device with driver and
    optional channel mapping, it is identified via usb using udev.

    This is used for devices which communicate over a custom USB protocol.

    Args:
        driver (str): driver to use with sigrok
        channels (str): a sigrok channel mapping as described in the sigrok-cli man page
    """
    driver = attr.ib(
        default=None,
        validator=attr.validators.instance_of(str)
    )
    channels = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str))
    )

    def __attrs_post_init__(self):
        self.match['@SUBSYSTEM'] = 'usb'
        super().__attrs_post_init__()

@target_factory.reg_resource
@attr.s(eq=False)
class SigrokUSBSerialDevice(USBResource):
    """The SigrokUSBSerialDevice describes an attached sigrok device with driver and
    optional channel mapping, it is identified via usb using udev.

    This is used for devices which communicate over an emulated serial device.

    Args:
        driver (str): driver to use with sigrok
        channels (str): a sigrok channel mapping as described in the sigrok-cli man page
    """
    driver = attr.ib(
        default=None,
        validator=attr.validators.instance_of(str)
    )
    channels = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str))
    )

    def __attrs_post_init__(self):
        self.match['SUBSYSTEM'] = 'tty'
        self.match['@SUBSYSTEM'] = 'usb'
        super().__attrs_post_init__()

    @property
    def path(self):
        if self.device is not None:
            return self.device.device_node

        return None

@target_factory.reg_resource
@attr.s(eq=False)
class USBSDWireDevice(USBResource):
    """The USBSDWireDevice describes an attached SDWire device,
    it is identified via USB using udev
    """

    control_path = attr.ib(
        default=None,
        validator=attr.validators.optional(str)
    )
    disk_path = attr.ib(
        default=None,
        validator=attr.validators.optional(str)
    )

    def __attrs_post_init__(self):
        self.match['ID_VENDOR_ID'] = '04e8'
        self.match['ID_MODEL_ID'] = '6001'
        self.match['@ID_VENDOR_ID'] = '0424'
        self.match['@ID_MODEL_ID'] = '2640'
        super().__attrs_post_init__()

    # Overwrite the avail attribute with our internal property
    @property
    def avail(self):
        return bool(self.disk_path and self.control_serial)

    # Forbid the USBResource super class to set the avail property
    @avail.setter
    def avail(self, prop):
        pass

    # Overwrite the poll function. Only mark the SDWire as available if both
    # paths are available.
    def poll(self):
        super().poll()
        if self.device is not None and not self.avail:
            for child in self.device.parent.children:
                if child.subsystem == 'block' and child.device_type == 'disk':
                    self.disk_path = child.device_node
            self.control_serial = self.device.properties.get('ID_SERIAL_SHORT')

    def update(self):
        super().update()
        if self.device is None:
            self.disk_path = None
            self.control_serial = None

    @property
    def path(self):
        return self.disk_path

@target_factory.reg_resource
@attr.s(eq=False)
class USBSDMuxDevice(USBResource):
    """The USBSDMuxDevice describes an attached USBSDMux device,
    it is identified via USB using udev
    """

    control_path = attr.ib(default=None)
    disk_path = attr.ib(default=None)

    def __attrs_post_init__(self):
        self.match['ID_VENDOR_ID'] = '0424'
        self.match['ID_MODEL_ID'] = '4041'
        super().__attrs_post_init__()

    # Overwrite the avail attribute with our internal property
    @property
    def avail(self):
        return bool(self.disk_path and self.control_path)

    # Forbid the USBResource super class to set the avail property
    @avail.setter
    def avail(self, prop):
        pass

    # Overwrite the poll function. Only mark the SDMux as available if both
    # paths are available.
    def poll(self):
        super().poll()
        if self.device is not None and not self.avail:
            for child in self.device.children:
                if child.subsystem == 'block' and child.device_type == 'disk':
                    self.disk_path = child.device_node
                elif child.subsystem == 'scsi_generic':
                    self.control_path = child.device_node

    def update(self):
        super().update()
        if self.device is None:
            self.control_path = None
            self.disk_path = None

    @property
    def path(self):
        return self.disk_path

@target_factory.reg_resource
@attr.s(eq=False)
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
@attr.s(eq=False)
class SiSPMPowerPort(USBResource):
    """This resource describes a SiS-PM (Silver Shield PM) power port.

    Args:
        index (int): port index
    """
    index = attr.ib(default=0, validator=attr.validators.instance_of(int))

    def filter_match(self, device):
        match = (device.properties.get('ID_VENDOR_ID'), device.properties.get('ID_MODEL_ID'))

        if match not in [
                ("04b4", "fd10"), ("04b4", "fd11"),
                ("04b4", "fd12"), ("04b4", "fd13"),
                ("04b4", "fd15")]:
            return False

        return super().filter_match(device)

@target_factory.reg_resource
@attr.s(eq=False)
class USBVideo(USBResource):
    def filter_match(self, device):
        capabilities = device.properties.get('ID_V4L_CAPABILITIES').split(':')

        if 'capture' not in capabilities:
            return False

        return super().filter_match(device)

    def __attrs_post_init__(self):
        self.match['SUBSYSTEM'] = 'video4linux'
        self.match['@SUBSYSTEM'] = 'usb'
        super().__attrs_post_init__()

    @property
    def path(self):
        if self.device is not None:
            return self.device.device_node

        return None

@target_factory.reg_resource
@attr.s(eq=False)
class USBAudioInput(USBResource):
    # the ALSA PCM device number (as in hw:CARD=<card>,DEV=<index>)
    index = attr.ib(default=0, validator=attr.validators.instance_of(int))

    def filter_match(self, device):
        suffix = f"D{self.index}c"

        if not device.sys_name.endswith(suffix):
            return False

        return super().filter_match(device)

    def __attrs_post_init__(self):
        self.match['SUBSYSTEM'] = 'sound'
        self.match['@SUBSYSTEM'] = 'usb'
        super().__attrs_post_init__()

    @property
    def path(self):
        "the device node (for example /dev/snd/pcmC3D0c)"
        if self.device is not None:
            return self.device.device_node

        return None

    @property
    def alsa_name(self):
        "the ALSA device name (for example hw:CARD=3,DEV=0)"
        if self.device is not None:
            return f"hw:CARD={self.device.parent.attributes.asint('number')},DEV={self.index}"

        return None

@target_factory.reg_resource
@attr.s(eq=False)
class USBTMC(USBResource):
    def __attrs_post_init__(self):
        self.match['SUBSYSTEM'] = 'usbmisc'
        self.match['@DRIVER'] = 'usbtmc'
        self.match['@SUBSYSTEM'] = 'usb'
        super().__attrs_post_init__()

    @property
    def path(self):
        if self.device is not None:
            return self.device.device_node

        return None

@target_factory.reg_resource
@attr.s(eq=False)
class DeditecRelais8(USBResource):
    index = attr.ib(default=None, validator=attr.validators.instance_of(int))
    invert = attr.ib(default=False, validator=attr.validators.instance_of(bool))

    def __attrs_post_init__(self):
        self.match['ID_VENDOR'] = 'DEDITEC'
        # Deditec does not set proper model/vendor IDs, so we use ID_MODEL instead
        self.match['ID_MODEL'] = 'DEDITEC_USB-OPT_REL-8'
        super().__attrs_post_init__()


@target_factory.reg_resource
@attr.s(eq=False)
class HIDRelay(USBResource):
    index = attr.ib(default=1, validator=attr.validators.instance_of(int))
    invert = attr.ib(default=False, validator=attr.validators.instance_of(bool))

    def filter_match(self, device):
        match = (device.properties.get('ID_VENDOR_ID'), device.properties.get('ID_MODEL_ID'))

        if match not in [("16c0", "05df"),  # dcttech USBRelay2
                         ("5131", "2007"),  # LC-US8
                         ]:
            return False

        return super().filter_match(device)

@target_factory.reg_resource
@attr.s(eq=False)
class USBFlashableDevice(USBResource):
    @property
    def devnode(self):
        if self.device is not None:
            return self.device.device_node
        return None

@target_factory.reg_resource
@attr.s(eq=False)
class LXAUSBMux(USBResource):
    """The LXAUSBMux describes an attached USBMux device,
    it is identified via USB using udev.
    """

    def __attrs_post_init__(self):
        self.match['ID_VENDOR_ID'] = '33f7'
        self.match['ID_MODEL_ID'] = '0001'
        super().__attrs_post_init__()

@target_factory.reg_resource
@attr.s(eq=False)
class USBDebugger(USBResource):
    def filter_match(self, device):
        match = (device.properties.get('ID_VENDOR_ID'), device.properties.get('ID_MODEL_ID'))

        if match not in [("0403", "6010"),  # FT2232C/D/H Dual UART/FIFO IC
                         ("0403", "6014"),  # FT232HL/Q
                         ("0483", "374b"),  # STLINK-V3
                         ("0483", "374f"),  # STLINK-V3
                         ("15ba", "0003"),  # Olimex ARM-USB-OCD
                         ("15ba", "002b"),  # Olimex ARM-USB-OCD-H
                         ("15ba", "0004"),  # Olimex ARM-USB-TINY
                         ("15ba", "002a"),  # Olimex ARM-USB-TINY-H
                         ("1366", "0101"),  # SEGGER J-Link PLUS
                         ("1366", "0105"),  # SEGGER J-Link
                         ("1366", "1015"),  # SEGGER J-Link
                         ("1366", "1051"),  # SEGGER J-Link
                         ]:
            return False

        return super().filter_match(device)

@target_factory.reg_resource
@attr.s(eq=False)
class MatchedSysfsGPIO(USBResource):
    """The MatchedSysfsGPIO described a SysfsGPIO matched by Udev

    Args:
        pin (int): gpio pin number within the matched gpiochip."""
    pin = attr.ib(default=None, validator=attr.validators.instance_of(int))
    index = None

    def __attrs_post_init__(self):
        self.match['SUBSYSTEM'] = 'gpio'
        super().__attrs_post_init__()

    def filter_match(self, device):
        # Filter out the char device
        if device.properties.get('DEVNAME') is not None:
            return False
        return super().filter_match(device)

    def update(self):
        super().update()
        if self.device is not None:
            if self.pin >= int(self.read_attr('ngpio')):
                raise ValueError("MatchedSysfsGPIO pin out of bound")
            self.index = int(self.read_attr('base')) + self.pin
        else:
            self.index = None
