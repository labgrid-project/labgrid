import pytest

from labgrid.driver.joulescopedriver import JoulescopeDriver
from labgrid.resource.common import ResourceManager
from labgrid.resource.joulescope import JOULESCOPE_MODELS, JoulescopeDevice
from labgrid.resource.remote import NetworkJoulescopeDevice

_MODEL_PID = {model: pid for pid, model in JOULESCOPE_MODELS.items()}


class FakeUdevDevice:
    """Minimal stand-in for a pyudev device exposing ``properties.get``."""

    def __init__(self, properties):
        self.properties = properties


@pytest.fixture(autouse=True)
def no_managers(mocker):
    """Use the inert base ResourceManager so resources never touch real udev or a coordinator."""
    mocker.patch.object(JoulescopeDevice, "manager_cls", ResourceManager)
    mocker.patch.object(NetworkJoulescopeDevice, "manager_cls", ResourceManager)


@pytest.fixture
def fake_agent(mocker):
    """Patch AgentWrapper so the driver talks to a fake agent proxy.

    ``wrapper`` is the AgentWrapper instance, ``proxy`` the loaded module proxy.
    ``AgentWrapper`` records the host it was constructed with in ``wrapper._host``.
    """
    proxy = mocker.MagicMock(name="proxy")
    wrapper = mocker.MagicMock(name="wrapper")
    wrapper.load.return_value = proxy

    def factory(host=None):
        wrapper._host = host
        return wrapper

    cls = mocker.patch("labgrid.driver.joulescopedriver.AgentWrapper", side_effect=factory)
    cls.wrapper = wrapper
    cls.proxy = proxy
    return cls


def make_device(target, serial="001234", model="js220"):
    """Create a local JoulescopeDevice with udev properties faked as if matched."""
    properties = {}
    if serial is not None:
        properties["ID_SERIAL_SHORT"] = serial
    if model is not None:
        properties["ID_MODEL_ID"] = _MODEL_PID[model]
    dev = JoulescopeDevice(target, "js")
    dev.device = FakeUdevDevice(properties)
    dev.avail = True
    return dev


def make_network_device(target, host="exporter", serial="001234", model="js220"):
    """Create a NetworkJoulescopeDevice as the coordinator would hand to a client."""
    dev = NetworkJoulescopeDevice(
        target,
        "js",
        host=host,
        busnum=None,
        devnum=None,
        path=None,
        vendor_id=None,
        model_id=None,
        serial=serial,
        model=model,
    )
    dev.avail = True
    return dev


def make_driver(target, fake_agent, network=False, **kwargs):
    if network:
        make_network_device(target)
    else:
        make_device(target)
    d = JoulescopeDriver(target, "jsdrv", **kwargs)
    target.activate(d)
    return d


def test_create(target, fake_agent):
    make_device(target)
    d = JoulescopeDriver(target, "jsdrv")
    assert isinstance(d, JoulescopeDriver)


def test_binds_local_and_network(target, fake_agent):
    # both resource types are accepted by the driver bindings
    assert JoulescopeDevice in JoulescopeDriver.bindings["device"]
    assert NetworkJoulescopeDevice in JoulescopeDriver.bindings["device"]


def test_activate_local_uses_local_agent(target, fake_agent):
    make_driver(target, fake_agent)
    # local device -> agent runs locally (host None)
    assert fake_agent.wrapper._host is None
    fake_agent.wrapper.load.assert_called_once_with("joulescope")
    fake_agent.proxy.open.assert_called_once_with("001234", "js220", 2.0)


def test_activate_network_uses_remote_agent(target, fake_agent):
    make_driver(target, fake_agent, network=True)
    # network device -> agent runs on the exporter host
    assert fake_agent.wrapper._host == "exporter"
    fake_agent.proxy.open.assert_called_once_with("001234", "js220", 2.0)


def test_activate_open_failure_closes_wrapper(target, fake_agent):
    make_device(target)
    fake_agent.proxy.open.side_effect = RuntimeError("no device")
    d = JoulescopeDriver(target, "jsdrv")
    with pytest.raises(RuntimeError):
        target.activate(d)
    # opening failed, so the agent subprocess must be cleaned up here since
    # on_deactivate() would not run for a driver that never became active
    fake_agent.wrapper.close.assert_called_once()
    assert d.wrapper is None
    assert d.proxy is None


def test_activate_passes_frequency(target, fake_agent):
    make_device(target)
    d = JoulescopeDriver(target, "jsdrv", frequency=10.0)
    target.activate(d)
    fake_agent.proxy.open.assert_called_once_with("001234", "js220", 10.0)


def test_get_statistics_delegates(target, fake_agent):
    d = make_driver(target, fake_agent)
    fake_agent.proxy.get_statistics.return_value = {"power": {"avg": 3.3}}
    assert d.get_statistics() == {"power": {"avg": 3.3}}
    fake_agent.proxy.get_statistics.assert_called_once_with("001234", "js220")


def test_start_stop_delegate(target, fake_agent):
    d = make_driver(target, fake_agent)
    fake_agent.proxy.stop.return_value = {"energy_J": 8.0, "charge_C": 3.0, "duration_s": 1.0}
    d.start()
    result = d.stop()
    fake_agent.proxy.start.assert_called_once_with("001234", "js220")
    fake_agent.proxy.stop.assert_called_once_with("001234", "js220")
    assert result["energy_J"] == 8.0


def test_power_on_off_delegate(target, fake_agent):
    d = make_driver(target, fake_agent)
    d.on()
    fake_agent.proxy.set_power.assert_any_call("001234", "js220", True)
    d.off()
    fake_agent.proxy.set_power.assert_any_call("001234", "js220", False)


def test_power_cycle(target, fake_agent, mocker):
    d = make_driver(target, fake_agent, delay=0.0)
    mocker.patch("labgrid.driver.joulescopedriver.time.sleep")
    d.cycle()
    calls = [c.args for c in fake_agent.proxy.set_power.call_args_list]
    assert ("001234", "js220", False) in calls
    assert ("001234", "js220", True) in calls


def test_capture_local(target, fake_agent):
    d = make_driver(target, fake_agent)
    d.capture("out.jls", signals=["current", "power"], duration=1.0)
    # local: the agent writes the file directly, no copy-back
    fake_agent.proxy.capture.assert_called_once_with("001234", "js220", "out.jls", ["current", "power"], 1.0, None)
    fake_agent.proxy.remove.assert_not_called()


def test_capture_remote_copies_back(target, fake_agent, mocker):
    d = make_driver(target, fake_agent, network=True)
    get_file = mocker.patch("labgrid.driver.joulescopedriver.sshmanager.get_file")
    d.capture("local.jls", duration=1.0)
    # remote: written to a temp path on the exporter, copied back, then removed
    remote = fake_agent.proxy.capture.call_args.args[2]
    assert remote.startswith("/tmp/labgrid-joulescope-")
    assert remote.endswith(".jls")
    get_file.assert_called_once_with("exporter", remote, "local.jls")
    fake_agent.proxy.remove.assert_called_once_with(remote)


def test_capture_requires_duration(target, fake_agent):
    d = make_driver(target, fake_agent)
    with pytest.raises(ValueError):
        d.capture("out.jls")
    fake_agent.proxy.capture.assert_not_called()


def test_deactivate_closes_proxy_and_wrapper(target, fake_agent):
    d = make_driver(target, fake_agent)
    target.deactivate(d)
    fake_agent.proxy.close.assert_called_once_with("001234", "js220")
    fake_agent.wrapper.close.assert_called_once()
