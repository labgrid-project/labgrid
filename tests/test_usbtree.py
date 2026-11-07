from labgrid.util.usbtree import (
    UsbDevice,
    format_hubs,
    get_controllers,
    parse_reg_cap,
    read_devices,
    read_xhci_limit,
)

REG_CAP = """CAPLENGTH = 0x01000080
HCSPARAMS1 = 0x1a000840
HCSPARAMS2 = 0x14200054
"""


def make_devices():
    """Make an EHCI controller with two levels of hubs and an xHCI one"""
    ehci = "/sys/devices/pci0000:00/0000:03:00.2/usb1"
    xhci = "/sys/devices/pci0000:00/0000:00:14.0"

    def dev(path, parent, ctrl, driver, ports=0, **kwargs):
        return UsbDevice(path=path, parent=parent, controller=ctrl, driver=driver, hub_ports=ports, **kwargs)

    return [
        dev(ehci, None, "0000:03:00.2", "ehci-pci", 5, busnum="001", id_path="pci-0000:03:00.2", speed="480"),
        dev(
            f"{ehci}/1-5",
            ehci,
            "0000:03:00.2",
            "ehci-pci",
            4,
            busnum="001",
            id_path="pci-0000:03:00.2-usb-0:5",
            usb_id="0bda:5411",
            product="4-Port USB 2.0 Hub",
            speed="480",
        ),
        dev(
            f"{ehci}/1-5/1-5.10",
            f"{ehci}/1-5",
            "0000:03:00.2",
            "ehci-pci",
            2,
            busnum="001",
            id_path="pci-0000:03:00.2-usb-0:5.10",
            speed="480",
        ),
        dev(
            f"{ehci}/1-5/1-5.2",
            f"{ehci}/1-5",
            "0000:03:00.2",
            "ehci-pci",
            2,
            busnum="001",
            id_path="pci-0000:03:00.2-usb-0:5.2",
            speed="480",
        ),
        # Not a hub, so only counted
        dev(f"{ehci}/1-5/1-5.1", f"{ehci}/1-5", "0000:03:00.2", "ehci-pci", busnum="001", speed="12"),
        dev(
            f"{xhci}/usb8",
            None,
            "0000:00:14.0",
            "xhci_hcd",
            10,
            busnum="008",
            id_path="pci-0000:00:14.0",
            speed="5000",
        ),
        dev(
            f"{xhci}/usb7", None, "0000:00:14.0", "xhci_hcd", 16, busnum="007", id_path="pci-0000:00:14.0", speed="480"
        ),
        dev(f"{xhci}/usb7/7-1", f"{xhci}/usb7", "0000:00:14.0", "xhci_hcd", busnum="007", speed="480"),
    ]


def test_parse_reg_cap():
    assert parse_reg_cap(REG_CAP) == 64
    assert parse_reg_cap("CAPLENGTH = 0x01000080\n") is None


def test_read_xhci_limit(tmp_path):
    regs = tmp_path / "usb" / "xhci" / "0000:00:14.0"
    regs.mkdir(parents=True)
    (regs / "reg-cap").write_text(REG_CAP)
    assert read_xhci_limit("0000:00:14.0", debugfs=str(tmp_path)) == 64
    assert read_xhci_limit("0000:04:00.0", debugfs=str(tmp_path)) is None


def test_get_controllers():
    xhci, ehci = get_controllers(make_devices(), read_limit=lambda name: 2)

    assert xhci.name == "0000:00:14.0"
    assert [root.busnum for root in xhci.roots] == ["007", "008"]
    assert xhci.devices == 1
    assert xhci.max_devices == 2

    assert ehci.name == "0000:03:00.2"
    assert ehci.devices == 4
    assert ehci.max_devices == 127


def test_format_hubs():
    devices = make_devices()
    lines = format_hubs(get_controllers(devices, read_limit=lambda name: 1), devices)
    assert lines == [
        "Controller 0000:00:14.0 (xhci_hcd): 1 of 1 device, FULL",
        "  BUS  PORTS  SPEED  ID_PATH           DEVICE",
        "  007  1/16   480M   pci-0000:00:14.0  ????:????",
        "  008  0/10   5G     pci-0000:00:14.0  ????:????",
        "",
        "Controller 0000:03:00.2 (ehci-pci): 4 of 127 devices, 123 free",
        "  BUS  PORTS  SPEED  ID_PATH                          DEVICE",
        "  001  1/5    480M   pci-0000:03:00.2                 ????:????",
        "  001  3/4    480M     pci-0000:03:00.2-usb-0:5       0bda:5411  4-Port USB 2.0 Hub",
        "  001  0/2    480M       pci-0000:03:00.2-usb-0:5.2   ????:????",
        "  001  0/2    480M       pci-0000:03:00.2-usb-0:5.10  ????:????",
        "",
    ]


def test_format_hubs_unknown_limit():
    devices = make_devices()
    lines = format_hubs(get_controllers(devices, read_limit=lambda name: None), devices)
    assert lines[0] == "Controller 0000:00:14.0 (xhci_hcd): 1 device, limit not known"
    assert lines[-1] == "Run as root to read the number of device slots of each xHCI controller"


class FakeAttributes:
    def __init__(self, values):
        self.values = values

    def asstring(self, name):
        return self.values[name]


class FakeDevice:
    def __init__(self, sys_path, parent, properties, attributes, driver=None):
        self.sys_path = sys_path
        self.sys_name = sys_path.rsplit("/", 1)[-1]
        self.parent = parent
        self.properties = properties
        self.attributes = FakeAttributes(attributes)
        self.driver = driver

    def find_parent(self, subsystem, device_type=None):
        if isinstance(self.parent, FakeDevice) and self.parent.properties.get("DEVTYPE") == device_type:
            return self.parent
        return None


class FakeContext:
    def __init__(self, devices):
        self.devices = devices

    def list_devices(self, **kwargs):
        assert kwargs == {"subsystem": "usb", "DEVTYPE": "usb_device"}
        return self.devices


def test_read_devices():
    pci = FakeDevice("/sys/devices/pci0000:00/0000:00:14.0", None, {}, {}, driver="xhci_hcd")
    root = FakeDevice(
        f"{pci.sys_path}/usb7",
        pci,
        {"DEVTYPE": "usb_device", "BUSNUM": "007", "ID_PATH": "pci-0000:00:14.0"},
        {"bDeviceClass": "09", "maxchild": "16", "idVendor": "1d6b", "idProduct": "0002", "speed": "480"},
    )
    hub = FakeDevice(
        f"{root.sys_path}/7-1",
        root,
        {"DEVTYPE": "usb_device", "BUSNUM": "007", "ID_PATH": "pci-0000:00:14.0-usb-0:1", "ID_VENDOR_ID": "2109"},
        {"bDeviceClass": "09", "maxchild": "4", "idProduct": "2817", "product": "USB2.0 Hub", "speed": "480"},
    )
    serial = FakeDevice(
        f"{hub.sys_path}/7-1.2",
        hub,
        {"DEVTYPE": "usb_device", "BUSNUM": "007", "ID_MODEL_FROM_DATABASE": "PL2303 Serial Port"},
        {"bDeviceClass": "00", "maxchild": "0", "speed": "12"},
    )

    devices = read_devices(FakeContext([root, hub, serial]))

    assert [(d.parent, d.controller, d.driver, d.hub_ports) for d in devices] == [
        (None, "0000:00:14.0", "xhci_hcd", 16),
        (root.sys_path, "0000:00:14.0", "xhci_hcd", 4),
        (hub.sys_path, "0000:00:14.0", "xhci_hcd", 0),
    ]
    assert devices[1].usb_id == "2109:2817"
    assert devices[1].product == "USB2.0 Hub"
    assert devices[2].usb_id == "????:????"
    assert devices[2].product == "PL2303 Serial Port"
