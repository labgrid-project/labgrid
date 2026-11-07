"""Read the USB topology of this host and describe its hubs

This backs ``labgrid-suggest --list-hubs``. It works in three steps:

- read_devices() uses udev to read each USB device into a UsbDevice, noting
  the hub it is plugged into, the host controller it sits below, its ID_PATH
  and, for a hub, how many ports it has
- get_controllers() groups the devices by host controller into Controller
  objects, counting the devices on each and working out the most it can have
- format_hubs() lists the hubs below each controller as a tree, showing how
  many of each hub's ports are in use and how full the controller is

The limit matters because a USB hub that stops working is often not faulty:
its host controller may have run out of room for more devices. An xHCI
controller has a fixed number of device slots shared by every device below
it, across both its USB 2 and USB 3 buses, which the kernel only exposes in
debugfs, so it can only be read with root access. Other controllers are
limited to the 127 addresses on their bus.

list_hubs() runs all three steps on this host.
"""

import re

import attr

# Device addresses on a USB bus are 7 bits wide and 0 is reserved
USB_BUS_MAX_DEVICES = 127

HCSPARAMS1_RE = re.compile(r"^HCSPARAMS1 = (0x[0-9a-fA-F]+)", re.MULTILINE)

DEBUGFS = "/sys/kernel/debug"


@attr.s(eq=False)
class UsbDevice:
    """A USB device, as seen in sysfs

    Args:
        path (str): sysfs path of the device
        parent (str): sysfs path of the hub it is plugged into, or None if it
            is a root hub
        controller (str): name of the host controller, e.g. a PCI address
        driver (str): driver of the host controller
        busnum (str): USB bus number
        id_path (str): udev ID_PATH, as used in resource matches
        usb_id (str): vendor and product ID, as 'vvvv:pppp'
        product (str): product name
        speed (str): speed in Mbit/s, as reported by sysfs
        hub_ports (int): number of downstream ports, 0 if it is not a hub
    """

    path = attr.ib()
    parent = attr.ib()
    controller = attr.ib()
    driver = attr.ib()
    busnum = attr.ib(default="")
    id_path = attr.ib(default="")
    usb_id = attr.ib(default="????:????")
    product = attr.ib(default="")
    speed = attr.ib(default="")
    hub_ports = attr.ib(default=0)


@attr.s(eq=False)
class Controller:
    """A USB host controller and the devices below it

    Args:
        name (str): device name, e.g. the PCI address
        driver (str): kernel driver, e.g. 'xhci_hcd'
        roots (list): root hubs (UsbDevice), one per bus
        devices (int): number of devices, not counting root hubs
        max_devices (int): most devices the controller supports, not counting
            root hubs, or None if not known
    """

    name = attr.ib()
    driver = attr.ib()
    roots = attr.ib(default=attr.Factory(list))
    devices = attr.ib(default=0)
    max_devices = attr.ib(default=None)

    @property
    def is_xhci(self):
        return "xhci" in (self.driver or "")


def _attr(dev, name):
    try:
        return dev.attributes.asstring(name)
    except (KeyError, UnicodeDecodeError):
        return ""


def read_devices(context=None):
    """Read the USB devices on this host

    Args:
        context (pyudev.Context): udev context to use, None to create one

    Returns:
        list of UsbDevice
    """
    import pyudev

    if context is None:
        context = pyudev.Context()
    result = []
    for dev in context.list_devices(subsystem="usb", DEVTYPE="usb_device"):
        parent = dev.find_parent("usb", "usb_device")
        root = dev
        while (up := root.find_parent("usb", "usb_device")) is not None:
            root = up
        hcd = root.parent
        vid = (
            dev.properties.get("ID_VENDOR_ID")
            or _attr(dev, "idVendor")
            or "????"
        )
        pid = (
            dev.properties.get("ID_MODEL_ID")
            or _attr(dev, "idProduct")
            or "????"
        )
        product = _attr(dev, "product") or dev.properties.get(
            "ID_MODEL_FROM_DATABASE", ""
        )
        is_hub = _attr(dev, "bDeviceClass") == "09"
        ports = _attr(dev, "maxchild")
        result.append(
            UsbDevice(
                path=dev.sys_path,
                parent=parent.sys_path if parent is not None else None,
                controller=hcd.sys_name if hcd is not None else "?",
                driver=hcd.driver if hcd is not None else None,
                busnum=dev.properties.get("BUSNUM", ""),
                id_path=dev.properties.get("ID_PATH", ""),
                usb_id=f"{vid}:{pid}",
                product=product,
                speed=_attr(dev, "speed"),
                hub_ports=int(ports) if is_hub and ports.isdigit() else 0,
            )
        )
    return result


def parse_reg_cap(text):
    """Find the number of device slots in an xHCI controller's capabilities

    Args:
        text (str): contents of the controller's reg-cap file in debugfs

    Returns:
        int: MaxSlots field of HCSPARAMS1, or None if it is not present
    """
    m = HCSPARAMS1_RE.search(text)
    return int(m.group(1), 16) & 0xFF if m else None


def read_xhci_limit(name, debugfs=DEBUGFS):
    """Read the number of device slots of an xHCI controller

    The kernel does not export this except in debugfs, which normally needs
    root access

    Args:
        name (str): controller name, e.g. a PCI address
        debugfs (str): where debugfs is mounted

    Returns:
        int: number of device slots, or None if it cannot be read
    """
    try:
        with open(f"{debugfs}/usb/xhci/{name}/reg-cap") as inf:
            return parse_reg_cap(inf.read())
    except OSError:
        return None


def get_controllers(devices, read_limit=read_xhci_limit):
    """Group USB devices by host controller

    Args:
        devices (list of UsbDevice): devices to group
        read_limit (function): reads the number of device slots of an xHCI
            controller, given its name; returns None if it cannot

    Returns:
        list of Controller, sorted by name
    """
    ctrls = {}
    for dev in devices:
        ctrl = ctrls.setdefault(
            dev.controller, Controller(dev.controller, dev.driver)
        )
        if dev.parent is None:
            ctrl.roots.append(dev)
        else:
            ctrl.devices += 1
    for ctrl in ctrls.values():
        ctrl.roots.sort(key=lambda d: _natural_key(d.busnum))
        if ctrl.is_xhci:
            ctrl.max_devices = read_limit(ctrl.name)
        else:
            ctrl.max_devices = USB_BUS_MAX_DEVICES
    return [ctrls[name] for name in sorted(ctrls, key=_natural_key)]


def _natural_key(text):
    return [
        int(s) if s.isdigit() else s for s in re.split(r"(\d+)", text or "")
    ]


def _plural(count):
    return f"{count} device" + ("" if count == 1 else "s")


def _speed(speed):
    try:
        mbits = float(speed)
    except ValueError:
        return "?"
    if mbits >= 1000:
        return f"{mbits / 1000:g}G"
    return f"{mbits:g}M"


def _add_hub_rows(rows, hub, children, depth):
    """Add a row for a hub, followed by rows for the hubs below it

    Args:
        rows (list of tuple): rows to add to
        hub (UsbDevice): hub to add
        children (dict): devices plugged into each hub, keyed by its path
        depth (int): number of hubs between this one and its root hub
    """
    kids = children.get(hub.path, [])
    rows.append(
        (
            hub.busnum,
            f"{len(kids)}/{hub.hub_ports}",
            _speed(hub.speed),
            "  " * depth + hub.id_path,
            f"{hub.usb_id}  {hub.product}".rstrip(),
        )
    )
    for kid in kids:
        if kid.hub_ports:
            _add_hub_rows(rows, kid, children, depth + 1)


def format_hubs(controllers, devices):
    """Describe the hubs below each controller

    Args:
        controllers (list of Controller): controllers to describe
        devices (list of UsbDevice): all USB devices

    Returns:
        list of str: lines of output
    """
    children = {}
    for dev in devices:
        if dev.parent is not None:
            children.setdefault(dev.parent, []).append(dev)
    for kids in children.values():
        kids.sort(key=lambda d: _natural_key(d.path))

    lines = []
    unknown = False
    for ctrl in controllers:
        if ctrl.max_devices is None:
            usage = f"{_plural(ctrl.devices)}, limit not known"
            unknown = True
        else:
            free = ctrl.max_devices - ctrl.devices
            usage = f"{ctrl.devices} of {_plural(ctrl.max_devices)}, "
            usage += "FULL" if free <= 0 else f"{free} free"
        lines.append(
            f"Controller {ctrl.name} ({ctrl.driver or 'no driver'}): {usage}"
        )

        rows = []
        for root in ctrl.roots:
            _add_hub_rows(rows, root, children, 0)

        headers = ("BUS", "PORTS", "SPEED", "ID_PATH", "DEVICE")
        widths = [
            max(len(r[i]) for r in [headers, *rows])
            for i in range(len(headers))
        ]
        for row in [headers, *rows]:
            lines.append(
                "  "
                + "  ".join(
                    c.ljust(w) for c, w in zip(row, widths, strict=True)
                ).rstrip()
            )
        lines.append("")
    if unknown:
        lines.append(
            "Run as root to read the number of device slots of each xHCI controller"
        )
    return lines


def list_hubs(context=None):
    """Describe the USB hubs on this host

    Args:
        context (pyudev.Context): udev context to use, None to create one

    Returns:
        list of str: lines of output
    """
    devices = read_devices(context)
    return format_hubs(get_controllers(devices), devices)
