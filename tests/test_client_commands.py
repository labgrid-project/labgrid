import pytest

from labgrid.exceptions import NoSupplierFoundError
from labgrid.remote.client import ensure_event_loop, ClientSession, UserError
from labgrid.driver import PyOCDDriver, NetworkPowerDriver, LXAIOBusPIODriver
from labgrid.resource.remote import NetworkUSBDebugger, NetworkLXAIOBusPIO
from labgrid.resource.power import NetworkPowerPort


class PseudoArgs:
    def __getattr__(self, attr):
        if attr == "action":
            return "get"
        if attr == "bootstrap_args":
            return ""
        return None


class PseudePlace:
    def __getattr__(self, attr):
        if attr == "name":
            return "PseudoPlace"
        return None


@pytest.fixture(scope="function")
def client(mocker, target):
    loop = ensure_event_loop()
    client = ClientSession(address="", loop=loop)
    client.args = PseudoArgs()
    place = PseudePlace()

    def get_acquired_place():
        return place
    place_mock = mocker.patch("labgrid.remote.client.ClientSession.get_acquired_place")
    place_mock.side_effect = get_acquired_place

    def _get_target(_):
        return target
    target_mock = mocker.patch("labgrid.remote.client.ClientSession._get_target")
    target_mock.side_effect = _get_target

    # disable resource updating
    target_resource_update_mock = mocker.patch("labgrid.target.Target.update_resources")
    return client


@pytest.mark.parametrize(
    "command",
    [
        "bootstrap",
        "digital_io",
        "power",
        "reset",
        "sd_mux",
        "usb_mux",
        "video",
    ],
)
def test_command_without_resources(client, command):
    with pytest.raises(UserError, match="target has no compatible resource available"):
        c = getattr(client, command)
        c()


@pytest.mark.parametrize(
    "command",
    [
        "dfu",
        "fastboot",
        "flashscript",
        "audio",
        "write_files",
        "write_image",
        "ssh",
        "scp",
        "rsync",
        "sshfs",
        "telnet",
    ],
)
def test_command_without_suplierers(client, command):
    with pytest.raises(NoSupplierFoundError):
        c = getattr(client, command)
        c()


def network_usb_ressource(target):
    network_args = {
        "name": "network_usb_ressource",
        "host": "None",
        "busnum": 0,
        "devnum": 0,
        "path": "1-12",
        "vendor_id": 0,
        "model_id": 0,
    }
    r = NetworkUSBDebugger(target, **network_args)
    r.avail = True


def pyocd_driver(target):
    network_usb_ressource(target)
    PyOCDDriver(target, "pyocd")


def network_power_port(target):
    network_args = {
        "name": "network_power_port",
        "host": "None",
        "model": "rest",
        "index": "0",
    }
    r = NetworkPowerPort(target, **network_args)
    r.avail = True


def network_power_driver(target):
    network_power_port(target)
    NetworkPowerDriver(target, "fake_power")


def network_LXA_gpio(target):
    network_args = {
        "name": "network_lxa_io_bus_name",
        "node": "network_lxa_io_bus_node",
        "host": "None",
        "pin": "0",
        "invert": False,
    }
    r = NetworkLXAIOBusPIO(target, **network_args)
    r.avail = True


def lxaio_bus_driver(target):
    network_LXA_gpio(target)
    LXAIOBusPIODriver(target, "lxa_pio_driver")


def power_and_gpio_ressource(target):
    network_LXA_gpio(target)
    network_power_port(target)


def power_gpio_and_debug_ressource(target):
    network_LXA_gpio(target)
    network_power_port(target)
    network_usb_ressource(target)


@pytest.mark.parametrize(
    "command,setup,patch",
    [
        ("reset", network_usb_ressource, "labgrid.driver.pyocddriver.PyOCDDriver.reset"),
        ("reset", pyocd_driver, "labgrid.driver.pyocddriver.PyOCDDriver.reset"),
        ("power", network_power_port, "labgrid.driver.power.rest.power_get"),
        ("power", network_power_driver, "labgrid.driver.power.rest.power_get"),
        ("digital_io", network_LXA_gpio, "labgrid.driver.lxaiobusdriver.LXAIOBusPIODriver.get"),
        ("digital_io", lxaio_bus_driver, "labgrid.driver.lxaiobusdriver.LXAIOBusPIODriver.get"),
        ("reset", network_power_port, "labgrid.driver.powerdriver.PowerResetMixin.reset"),
        ("reset", network_LXA_gpio, "labgrid.driver.resetdriver.DigitalOutputResetDriver.reset"),
        ("reset", power_and_gpio_ressource, "labgrid.driver.resetdriver.DigitalOutputResetDriver.reset"),
        ("reset", power_gpio_and_debug_ressource, "labgrid.driver.pyocddriver.PyOCDDriver.reset"),
        ("bootstrap", network_usb_ressource, "labgrid.driver.pyocddriver.PyOCDDriver.load"),
        ("bootstrap", pyocd_driver, "labgrid.driver.pyocddriver.PyOCDDriver.load"),
    ],
)
def test_reset_command_with_remote_resource(target, client, mocker, command, setup, patch):
    setup(target)

    driver_mock = mocker.patch(patch)

    c = getattr(client, command)
    c()

    driver_mock.assert_called_once()
