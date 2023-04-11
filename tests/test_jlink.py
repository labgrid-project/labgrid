import contextlib
import io
import pytest
import subprocess
from unittest.mock import MagicMock
from unittest.mock import Mock
from unittest.mock import patch

from labgrid.remote.exporter import USBJLinkExport
from labgrid.resource.remote import NetworkJLinkDevice
from labgrid.resource.udev import JLinkDevice
from labgrid.driver.jlinkdriver import JLinkDriver

FAKE_SERIAL = 123456789
MATCH = {"ID_SERIAL_SHORT": f"000{FAKE_SERIAL}"}


class Popen_mock():
    """Mock of Popen object to mimmic JLinkRemoteServer output"""

    def __init__(self, args, **kwargs):
        assert "JLinkRemoteServer" in args[0]
        assert args[1] == "-Port"
        # Since args[2] is dynamic do not check it
        assert args[3] == "-select"
        assert args[4] == f"USB={FAKE_SERIAL}"
        self.wait_called = False

    stdout = io.StringIO(
        "SEGGER J-Link Remote Server V7.84a\n"
        "Compiled Dec 22 2022 16:13:52\n"
        "\n"
        "'q' to quit '?' for help\n"
        "\n"
        f"Connected to J-Link with S/N {FAKE_SERIAL}\n"
        "\n"
        "Waiting for client connections...\n"
    )

    def communicate(self, input=None, timeout=None):
        # Only timeout on the first call to exercise the error handling code.
        if not self.wait_called:
            self.wait_called = True
            raise subprocess.TimeoutExpired("JLinkRemoteServer", timeout)

    def kill(self):
        pass

    def poll(self):
        return 0

    def terminate(self):
        pass


def test_jlink_resource(target):
    r = JLinkDevice(target, name=None, match=MATCH)


@patch('subprocess.Popen', Popen_mock)
def test_jlink_export_start(target):
    config = {'avail': True, 'cls': "JLinkDevice", 'params': {'match': MATCH}, }
    e = USBJLinkExport(config)
    e.local.avail = True
    e.local.serial = FAKE_SERIAL

    e.start()
    # Exercise the __del__ method which also exercises stop()
    del e


@patch('subprocess.Popen', Popen_mock)
def test_jlink_driver(target):
    pytest.importorskip("pylink")
    device = JLinkDevice(target, name=None, match=MATCH)
    device.avail = True
    device.serial = FAKE_SERIAL
    driver = JLinkDriver(target, name=None)

    with patch('pylink.JLink') as JLinkMock:
        instance = JLinkMock.return_value
        target.activate(driver)
        instance.open.assert_called_once_with(serial_no=FAKE_SERIAL)
        intf = driver.get_interface()
        assert(isinstance(intf, Mock))
        target.deactivate(driver)
        instance.close.assert_called_once_with()


@patch('subprocess.Popen', Popen_mock)
def test_jlink_driver_network_device(target):
    pytest.importorskip("pylink")
    device = NetworkJLinkDevice(target, None, host='127.0.1.1', port=12345, busnum=0, devnum=1,  path='0:1', vendor_id=0x0, model_id=0x0,)
    device.avail = True
    driver = JLinkDriver(target, name=None)
    assert (isinstance(driver, JLinkDriver))

    with patch('pylink.JLink') as JLinkMock:
        instance = JLinkMock.return_value
        # Call on_activate directly since activating the driver via the target does not work during testing
        driver.on_activate()
        instance.open.assert_called_once_with(ip_addr='127.0.0.1:12345')
        driver.on_deactivate()
        instance.close.assert_called_once_with()
