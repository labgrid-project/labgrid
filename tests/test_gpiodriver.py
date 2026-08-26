import types

import labgrid.driver.gpiodriver as gpiodriver
from labgrid.driver.gpiodriver import GpioDigitalInputDriver, GpioDigitalOutputDriver
from labgrid.remote.client import ClientSession
from labgrid.resource.common import ResourceManager
from labgrid.resource.remote import NetworkSysfsGPIO
from labgrid.resource import SysfsGPIO


class FakeWrapper:
    def __init__(self, host, proxy):
        self.host = host
        self.proxy = proxy

    def load(self, name):
        assert name == 'sysfsgpio'
        return self.proxy

    def close(self):
        pass


def test_gpio_input_driver_get(target, monkeypatch):
    proxy = types.SimpleNamespace(calls=[])

    def proxy_get(index, invert, direction):
        proxy.calls.append((index, invert, direction))
        return True

    proxy.get = proxy_get

    monkeypatch.setattr(gpiodriver, "AgentWrapper", lambda host: FakeWrapper(host, proxy))

    SysfsGPIO(target, name=None, index=13, invert=True)
    driver = GpioDigitalInputDriver(target, name=None)

    target.activate(driver)

    assert driver.get() is True
    assert proxy.calls == [(13, True, 'in')]

    target.deactivate(driver)


def test_gpio_output_driver_implements_digital_input_protocol(target):
    SysfsGPIO(target, name=None, index=13, invert=False)
    driver = GpioDigitalOutputDriver(target, name=None)

    assert target.get_driver("DigitalInputProtocol", activate=False) is driver


def test_client_io_get_uses_configured_gpio_input_driver(target, monkeypatch, capsys):
    proxy = types.SimpleNamespace(calls=[])

    def proxy_get(index, invert, direction):
        proxy.calls.append((index, invert, direction))
        return True

    proxy.get = proxy_get

    monkeypatch.setattr(gpiodriver, "AgentWrapper", lambda host: FakeWrapper(host, proxy))

    SysfsGPIO(target, name="gpio_in", index=13, invert=False)
    GpioDigitalInputDriver(target, name="gpio_in")

    session = object.__new__(ClientSession)
    session.args = types.SimpleNamespace(action="get", name="gpio_in")
    session.get_acquired_place = lambda: types.SimpleNamespace(name="test")
    session._get_target = lambda place: target

    session.digital_io()

    assert "digital IO gpio_in for place test is high" in capsys.readouterr().out
    assert proxy.calls == [(13, False, 'in')]


def test_client_io_get_keeps_network_sysfs_output_fallback(target, monkeypatch, mocker):
    monkeypatch.setattr(NetworkSysfsGPIO, "manager_cls", ResourceManager)
    driver = types.SimpleNamespace(get=mocker.MagicMock(return_value=False))
    session = object.__new__(ClientSession)
    session.args = types.SimpleNamespace(action="get", name="gpio")
    session.get_acquired_place = lambda: types.SimpleNamespace(name="test")
    session._get_target = lambda place: target
    session._get_driver_or_new = mocker.MagicMock(return_value=driver)

    NetworkSysfsGPIO(target, name="gpio", host="exporter", index=13, invert=False)

    session.digital_io()

    session._get_driver_or_new.assert_called_once_with(target, "GpioDigitalOutputDriver", name="gpio")
    driver.get.assert_called_once_with()
