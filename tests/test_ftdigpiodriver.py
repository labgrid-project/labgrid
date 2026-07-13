import types

import pytest

from labgrid.driver import ftdigpiodriver
from labgrid.driver.ftdigpiodriver import FTDIGPIODriver
from labgrid.remote.client import ClientSession
from labgrid.resource.common import ResourceManager
from labgrid.resource.remote import NetworkFTDIGPIO
from labgrid.resource.udev import FTDIGPIO


def test_ftdigpio_resource_create(target, monkeypatch):
    monkeypatch.setattr(FTDIGPIO, "manager_cls", ResourceManager)
    resource = FTDIGPIO(target, name=None, index=0, interface=1)

    assert resource.index == 0
    assert resource.interface == 1
    assert resource.match["DEVTYPE"] == "usb_device"


def test_ftdigpio_resource_validates_range(target, monkeypatch):
    monkeypatch.setattr(FTDIGPIO, "manager_cls", ResourceManager)

    with pytest.raises(ValueError):
        FTDIGPIO(target, name=None, index=8, interface=1)

    with pytest.raises(ValueError):
        FTDIGPIO(target, name=None, index=0, interface=0)


def test_ftdigpio_resource_filters_supported_devices(target, monkeypatch):
    monkeypatch.setattr(FTDIGPIO, "manager_cls", ResourceManager)
    resource = FTDIGPIO(target, name=None)

    def device(vendor_id, model_id):
        return types.SimpleNamespace(
            device_type="usb_device",
            properties={
                "ID_VENDOR_ID": vendor_id,
                "ID_MODEL_ID": model_id,
            },
        )

    assert resource.filter_match(device("0403", "6014")) is True
    assert resource.filter_match(device("0403", "6010")) is True
    assert resource.filter_match(device("0403", "6011")) is True
    assert resource.filter_match(device("0403", "6001")) is False


def test_ftdigpio_driver_create(target, monkeypatch):
    monkeypatch.setattr(NetworkFTDIGPIO, "manager_cls", ResourceManager)
    NetworkFTDIGPIO(
        target,
        name=None,
        host="exporter",
        busnum=1,
        devnum=39,
        path="1-12.4.2",
        vendor_id=0x0403,
        model_id=0x6014,
        index=0,
        interface=1,
    )

    driver = FTDIGPIODriver(target, name=None)

    assert isinstance(driver, FTDIGPIODriver)


def test_ftdigpio_driver_set_get(target, monkeypatch):
    monkeypatch.setattr(NetworkFTDIGPIO, "manager_cls", ResourceManager)
    proxy = types.SimpleNamespace(calls=[], value=False)

    def proxy_set(vendor_id, model_id, busnum, devnum, interface, index, status):
        proxy.calls.append((vendor_id, model_id, busnum, devnum, interface, index, status))
        proxy.value = status

    def proxy_get(vendor_id, model_id, busnum, devnum, interface, index):
        proxy.calls.append((vendor_id, model_id, busnum, devnum, interface, index))
        return proxy.value

    proxy.set = proxy_set
    proxy.get = proxy_get
    proxy.close = lambda: None

    class FakeWrapper:
        def __init__(self, host):
            self.host = host

        def load(self, name):
            assert name == "ftdigpio"
            return proxy

        def close(self):
            pass

    monkeypatch.setattr(ftdigpiodriver, "AgentWrapper", FakeWrapper)
    ftdigpiodriver._shared_agents.clear()

    resource = NetworkFTDIGPIO(
        target,
        name=None,
        host="exporter",
        busnum=1,
        devnum=39,
        path="1-12.4.2",
        vendor_id=0x0403,
        model_id=0x6014,
        index=2,
        interface=1,
        invert=True,
    )
    resource.avail = True
    driver = FTDIGPIODriver(target, name=None)

    target.activate(driver)
    driver.set(True)
    assert proxy.calls[-1] == (0x0403, 0x6014, 1, 39, 1, 2, False)
    assert driver.get() is True

    target.deactivate(driver)


def test_ftdigpio_agent(monkeypatch):
    from labgrid.util.agents import ftdigpio

    class FakeEndpoint:
        def __init__(self, address):
            self.bEndpointAddress = address
            self.writes = []

        def write(self, data, timeout=None):
            self.writes.append(bytes(data))

    out_ep = FakeEndpoint(0x02)
    in_ep = FakeEndpoint(0x81)

    class FakeConfig:
        def __getitem__(self, item):
            assert item == (0, 0)
            return [out_ep, in_ep]

    class FakeDevice:
        bus = 1
        address = 39

        def __init__(self):
            self.control = []
            self.detached = []
            self.released = []
            self.pins = b"\x00"

        def set_configuration(self):
            pass

        def is_kernel_driver_active(self, interface):
            assert interface == 0
            return False

        def detach_kernel_driver(self, interface):
            self.detached.append(interface)

        def get_active_configuration(self):
            return FakeConfig()

        def ctrl_transfer(self, request_type, request, value, index, data, timeout=None):
            self.control.append((request_type, request, value, index, data))
            if request_type == ftdigpio.IN_REQTYPE and request == ftdigpio.SIO_READ_PINS:
                return self.pins
            return None

    device = FakeDevice()
    monkeypatch.setattr(ftdigpio.usb.core, "find", lambda **kwargs: [device])
    monkeypatch.setattr(ftdigpio.usb.util, "claim_interface", lambda dev, interface: None)
    monkeypatch.setattr(
        ftdigpio.usb.util,
        "release_interface",
        lambda dev, interface: device.released.append(interface),
    )
    monkeypatch.setattr(ftdigpio.usb.util, "dispose_resources", lambda dev: None)

    device.pins = b"\x02"
    assert ftdigpio.handle_set(0x0403, 0x6014, 1, 39, 1, 2, True) is True
    assert device.control[-1] == (
        ftdigpio.OUT_REQTYPE,
        ftdigpio.SIO_SET_BITMODE,
        0x01ff,
        1,
        None,
    )
    assert out_ep.writes[-1] == b"\x06"

    device.pins = b"\x06"
    ftdigpio.handle_set(0x0403, 0x6014, 1, 39, 1, 3, True)
    assert device.control[-1] == (
        ftdigpio.OUT_REQTYPE,
        ftdigpio.SIO_SET_BITMODE,
        0x01ff,
        1,
        None,
    )
    assert out_ep.writes[-1] == b"\x0e"

    device.pins = b"\x02"
    ftdigpio.handle_set(0x0403, 0x6014, 1, 39, 1, 2, False)
    assert out_ep.writes[-1] == b"\x02"

    device.pins = b"\x08"
    assert ftdigpio.handle_get(0x0403, 0x6014, 1, 39, 1, 3) is True
    assert ftdigpio.handle_get(0x0403, 0x6014, 1, 39, 1, 2) is False
    assert device.released == [0, 0, 0, 0, 0]
    assert ftdigpio.handle_close() is True


def test_ftdigpio_agent_rejects_empty_pin_read(monkeypatch):
    from labgrid.util.agents import ftdigpio

    class FakeEndpoint:
        def __init__(self, address):
            self.bEndpointAddress = address

        def write(self, data, timeout=None):
            pass

    out_ep = FakeEndpoint(0x02)
    in_ep = FakeEndpoint(0x81)

    class FakeConfig:
        def __getitem__(self, item):
            assert item == (0, 0)
            return [out_ep, in_ep]

    class FakeDevice:
        bus = 1
        address = 39

        def set_configuration(self):
            pass

        def is_kernel_driver_active(self, interface):
            return False

        def get_active_configuration(self):
            return FakeConfig()

        def ctrl_transfer(self, request_type, request, value, index, data, timeout=None):
            if request_type == ftdigpio.IN_REQTYPE and request == ftdigpio.SIO_READ_PINS:
                return b""
            return None

    device = FakeDevice()
    monkeypatch.setattr(ftdigpio.usb.core, "find", lambda **kwargs: [device])
    monkeypatch.setattr(ftdigpio.usb.util, "claim_interface", lambda dev, interface: None)
    monkeypatch.setattr(ftdigpio.usb.util, "release_interface", lambda dev, interface: None)
    monkeypatch.setattr(ftdigpio.usb.util, "dispose_resources", lambda dev: None)

    with pytest.raises(TimeoutError, match="no data"):
        ftdigpio.handle_get(0x0403, 0x6014, 1, 39, 1, 3)


def test_ftdigpio_agent_rejects_unsupported_index():
    from labgrid.util.agents import ftdigpio

    with pytest.raises(ValueError, match="0-7"):
        ftdigpio.FTDIGPIO._validate_index(8)


def test_ftdigpio_agent_validates_supported_devices():
    from labgrid.util.agents import ftdigpio

    ftdigpio.FTDIGPIO._validate_device(0x0403, 0x6010, 2)
    ftdigpio.FTDIGPIO._validate_device(0x0403, 0x6011, 4)
    ftdigpio.FTDIGPIO._validate_device(0x0403, 0x6014, 1)

    with pytest.raises(ValueError, match="Unsupported"):
        ftdigpio.FTDIGPIO._validate_device(0x0403, 0x6001, 1)

    with pytest.raises(ValueError, match="interface"):
        ftdigpio.FTDIGPIO._validate_device(0x0403, 0x6014, 2)


def test_ftdigpio_export_params():
    from labgrid.remote.exporter import USBFTDIGPIOExport

    export = object.__new__(USBFTDIGPIOExport)
    export.host = "exporter"
    export.local = types.SimpleNamespace(
        busnum=1,
        devnum=39,
        path="1-12.4.2",
        vendor_id=0x0403,
        model_id=0x6014,
        index=2,
        interface=1,
        invert=True,
    )

    assert export._get_params() == {
        "host": "exporter",
        "busnum": 1,
        "devnum": 39,
        "path": "1-12.4.2",
        "vendor_id": 0x0403,
        "model_id": 0x6014,
        "index": 2,
        "interface": 1,
        "invert": True,
    }


def test_ftdigpio_client_digital_io(target, mocker, monkeypatch):
    monkeypatch.setattr(NetworkFTDIGPIO, "manager_cls", ResourceManager)
    driver = types.SimpleNamespace(set=mocker.MagicMock())
    session = object.__new__(ClientSession)
    session.args = types.SimpleNamespace(action="high", name=None)
    session.get_acquired_place = lambda: types.SimpleNamespace(name="test")
    session._get_target = lambda place: target
    session._get_driver_or_new = mocker.MagicMock(return_value=driver)

    NetworkFTDIGPIO(
        target,
        name=None,
        host="exporter",
        busnum=1,
        devnum=39,
        path="1-12.4.2",
        vendor_id=0x0403,
        model_id=0x6014,
        index=2,
        interface=1,
    )

    session.digital_io()

    session._get_driver_or_new.assert_called_once_with(target, "FTDIGPIODriver", name=None)
    driver.set.assert_called_once_with(True)


def test_ftdigpio_client_digital_io_get(target, mocker, monkeypatch, capsys):
    monkeypatch.setattr(NetworkFTDIGPIO, "manager_cls", ResourceManager)
    driver = types.SimpleNamespace(get=mocker.MagicMock(return_value=True))
    session = object.__new__(ClientSession)
    session.args = types.SimpleNamespace(action="get", name=None)
    session.get_acquired_place = lambda: types.SimpleNamespace(name="test")
    session._get_target = lambda place: target
    session._get_driver_or_new = mocker.MagicMock(return_value=driver)

    NetworkFTDIGPIO(
        target,
        name=None,
        host="exporter",
        busnum=1,
        devnum=39,
        path="1-12.4.2",
        vendor_id=0x0403,
        model_id=0x6014,
        index=2,
        interface=1,
    )

    session.digital_io()

    session._get_driver_or_new.assert_called_once_with(target, "FTDIGPIODriver", name=None)
    assert "digital IO for place test is high" in capsys.readouterr().out
