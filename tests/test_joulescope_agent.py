"""Unit tests for the Joulescope agent module (labgrid/util/agents/joulescope.py).

The agent holds all pyjoulescope_driver interaction and runs on the host the
device is attached to.  A fake ``pyjoulescope_driver`` is injected via
``sys.modules`` so these tests run without the real package or hardware.
"""

import importlib
import sys

import pytest


def make_sample(charge=0.0, energy=0.0, utc=(0, 1 << 30)):
    """Build a statistics value mimicking pyjoulescope_driver's s/stats/value."""

    def sig(avg, std, lo, hi):
        return {
            "avg": {"value": avg},
            "std": {"value": std},
            "min": {"value": lo},
            "max": {"value": hi},
        }

    return {
        "signals": {
            "current": sig(1.0, 0.1, 0.5, 1.5),
            "voltage": sig(3.3, 0.01, 3.2, 3.4),
            "power": sig(3.3, 0.1, 1.6, 5.0),
        },
        "accumulators": {
            "charge": {"value": charge},
            "energy": {"value": energy},
        },
        "time": {
            "utc": {"value": list(utc)},
            "samples": {"value": [0, 1000]},
        },
    }


@pytest.fixture
def agent(mocker):
    fake = mocker.MagicMock(name="pyjoulescope_driver")
    jsdrv = mocker.MagicMock(name="Driver")
    fake.Driver.return_value = jsdrv
    jsdrv.device_paths.return_value = ["u/js220/001234"]
    fake.time64.as_timestamp.side_effect = lambda t: t / float(1 << 30)

    mocker.patch.dict(sys.modules, {"pyjoulescope_driver": fake})
    mod = importlib.import_module("labgrid.util.agents.joulescope")
    mod = importlib.reload(mod)  # rebind module global to the fake
    mod._sessions.clear()

    state = {"cb": None, "samples": []}

    def subscribe(topic, flags, fn):
        state["cb"] = fn

    jsdrv.subscribe.side_effect = subscribe

    def sleep(_duration):
        # deliver the next queued sample through the stored subscription callback,
        # mirroring how the device thread feeds _wait_for_statistics()
        if state["samples"] and state["cb"] is not None:
            path = jsdrv.device_paths.return_value[0]
            state["cb"](path + "/s/stats/value", state["samples"].pop(0))

    mocker.patch.object(mod.time, "sleep", side_effect=sleep)

    fake._jsdrv = jsdrv
    fake._state = state
    return mod, fake


def make_session(agent, serial="001234", model="js220", frequency=2.0):
    mod, _ = agent
    return mod.JoulescopeSession(serial, model, frequency)


def test_open_configures_and_subscribes(agent):
    _, fake = agent
    make_session(agent)
    fake._jsdrv.open.assert_called_once_with("u/js220/001234")
    fake._jsdrv.publish.assert_any_call("u/js220/001234/s/stats/ctrl", 1)
    fake._jsdrv.subscribe.assert_called_once()


def test_resolve_no_match(agent):
    with pytest.raises(RuntimeError):
        make_session(agent, serial="999999")


def test_resolve_multiple(agent):
    _, fake = agent
    fake._jsdrv.device_paths.return_value = ["u/js220/001234", "u/js220/005678"]
    with pytest.raises(RuntimeError):
        make_session(agent, serial=None)


def test_get_statistics(agent):
    _, fake = agent
    s = make_session(agent)
    fake._state["samples"] = [make_sample(charge=2.0, energy=5.0)]
    stats = s.get_statistics()
    assert stats["current"]["avg"] == 1.0
    assert stats["voltage"]["avg"] == 3.3
    assert stats["power"]["max"] == 5.0
    assert stats["charge_C"] == 2.0
    assert stats["energy_J"] == 5.0


def test_start_stop_accumulation(agent):
    _, fake = agent
    s = make_session(agent)
    fake._state["samples"] = [
        make_sample(charge=1.0, energy=2.0, utc=(0, 0)),
        make_sample(charge=4.0, energy=10.0, utc=(0, 1 << 30)),  # +1 second
    ]
    s.start()
    result = s.stop()
    assert result["charge_C"] == pytest.approx(3.0)
    assert result["energy_J"] == pytest.approx(8.0)
    assert result["duration_s"] == pytest.approx(1.0)


def test_stop_without_start(agent):
    _, fake = agent
    s = make_session(agent)
    fake._state["samples"] = [make_sample()]
    with pytest.raises(RuntimeError):
        s.stop()


def test_capture(agent, mocker):
    _, fake = agent
    s = make_session(agent)
    recorder = mocker.MagicMock(name="Record")
    fake.Record.return_value = recorder
    result = s.capture("out.jls", signals=["current", "power"], duration=0)
    fake.Record.assert_called_once_with(fake._jsdrv, "u/js220/001234", signals=["current", "power"])
    recorder.open.assert_called_once_with("out.jls")
    recorder.close.assert_called_once()
    assert result == "out.jls"


def test_capture_requires_duration(agent):
    s = make_session(agent)
    with pytest.raises(ValueError):
        s.capture("out.jls")


def test_power_js110(agent):
    _, fake = agent
    fake._jsdrv.device_paths.return_value = ["u/js110/000111"]
    s = make_session(agent, serial="000111", model="js110")
    s.set_power(True)
    fake._jsdrv.publish.assert_any_call("u/js110/000111/s/i/range/select", "auto")
    s.set_power(False)
    fake._jsdrv.publish.assert_any_call("u/js110/000111/s/i/range/select", "off")


def test_power_js220(agent):
    _, fake = agent
    s = make_session(agent)
    s.set_power(False)
    fake._jsdrv.publish.assert_any_call("u/js220/001234/s/i/range/mode", "off")
    s.set_power(True)
    fake._jsdrv.publish.assert_any_call("u/js220/001234/s/i/range/mode", "auto")


def test_power_js320(agent):
    _, fake = agent
    fake._jsdrv.device_paths.return_value = ["u/js320/8w2a"]
    s = make_session(agent, serial="8w2a", model="js320")
    s.set_power(False)
    fake._jsdrv.publish.assert_any_call("u/js320/8w2a/s/i/range/mode", "off")


def test_close(agent):
    _, fake = agent
    s = make_session(agent)
    s.close()
    fake._jsdrv.close.assert_called_once_with("u/js220/001234")
    fake._jsdrv.finalize.assert_called_once()


def test_handlers_open_get_close(agent):
    mod, fake = agent
    fake._state["samples"] = [make_sample(charge=2.0, energy=5.0)]
    assert mod.handle_open("001234", "js220", 2.0) is True
    # opening again reuses the existing session
    mod.handle_open("001234", "js220", 2.0)
    fake.Driver.assert_called_once()
    stats = mod.handle_get_statistics("001234", "js220")
    assert stats["charge_C"] == 2.0
    mod.handle_close("001234", "js220")
    fake._jsdrv.close.assert_called_once_with("u/js220/001234")
