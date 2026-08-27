"""Hardware-in-the-loop tests for the Joulescope driver.

These talk to a real Joulescope (JS110/JS220/JS320) over USB and are skipped
unless ``--joulescope`` is passed.  They live in their own module so they use
the real udev ``ManagedResource`` machinery instead of the mocks in
``test_joulescopedriver.py``.
"""

import pytest

from labgrid import Target
from labgrid.driver.joulescopedriver import JoulescopeDriver
from labgrid.resource.joulescope import JOULESCOPE_MODELS, JoulescopeDevice

pytestmark = pytest.mark.joulescope


@pytest.fixture
def driver():
    t = Target("js")
    dev = JoulescopeDevice(t, "dev")
    d = JoulescopeDriver(t, "jsdrv", frequency=10.0)
    t.activate(d)
    yield dev, d
    t.deactivate(d)


def test_resource_matched(driver):
    dev, _ = driver
    assert dev.avail
    assert dev.model in JOULESCOPE_MODELS.values()
    assert dev.serial


def test_get_statistics(driver):
    _, d = driver
    stats = d.get_statistics()
    for signal in ("current", "voltage", "power"):
        assert set(stats[signal]) == {"avg", "std", "min", "max"}
        assert isinstance(stats[signal]["avg"], float)
    assert isinstance(stats["charge_C"], float)
    assert isinstance(stats["energy_J"], float)


def test_start_stop_window(driver):
    import time

    _, d = driver
    d.start()
    time.sleep(1.0)
    window = d.stop()
    assert set(window) == {"energy_J", "charge_C", "duration_s"}
    # the window is quantized to the statistics period (0.1 s at 10 Hz)
    assert 0.9 < window["duration_s"] < 1.3


def test_capture(driver, tmp_path):
    _, d = driver
    filename = str(tmp_path / "capture.jls")
    d.capture(filename, duration=0.5)

    pyjls = pytest.importorskip("pyjls")
    with pyjls.Reader(filename) as r:
        names = [s.name for s in r.signals.values()]
    for signal in ("current", "voltage", "power"):
        assert signal in names


def test_power_switch(driver):
    _, d = driver
    # exercises the JS220/JS320 s/i/range/mode (or JS110 s/i/range/select) path
    d.off()
    d.on()
    d.cycle()
