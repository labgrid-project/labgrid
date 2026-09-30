"""
This module runs pyjoulescope_driver on the host the Joulescope is physically
connected to, so the device can be shared over labgrid's distributed
infrastructure.  The JoulescopeDriver talks to it through the AgentWrapper, both
for local devices (agent runs as a local subprocess) and for remote devices
(agent runs on the exporter over SSH).

Supported functionality:

- stream measurement statistics (current, voltage, power, charge, energy)
- accumulate charge/energy over a start()/stop() window
- capture high-rate samples to a JLS file
- switch downstream power (PowerProtocol)

Only stdlib and pyjoulescope_driver are used so the module stays self-contained
when copied to the exporter.
"""

import contextlib
import os
import time

import pyjoulescope_driver


class JoulescopeSession:
    """Encapsulates a single opened Joulescope and its statistics stream."""

    def __init__(self, serial, model, frequency):
        self._pyjsdrv = pyjoulescope_driver
        self.serial = serial
        self.model = model
        self.frequency = frequency
        self._latest = None
        self._accum = None
        # pyjoulescope_driver matches subscriptions by callback identity, so the
        # exact same bound method must be passed to subscribe and unsubscribe.
        self._stats_cb = self._on_statistics
        self._jsdrv = self._pyjsdrv.Driver()
        self._path = self._resolve_path(self._jsdrv.device_paths())
        # ``model`` may have been None (match any); derive it from the path.
        self._model = self._path.split("/")[1]
        self._jsdrv.open(self._path)
        self._configure_statistics()

    # -- life cycle ---------------------------------------------------------

    def _resolve_path(self, paths):
        serial, model = self.serial, self.model
        matches = [p for p in paths if (serial is None or serial in p) and (model is None or f"/{model}/" in p)]
        if not matches:
            raise RuntimeError(f"No Joulescope matching serial={serial!r} model={model!r} found in {paths}")
        if len(matches) > 1:
            raise RuntimeError(f"Multiple Joulescopes match serial={serial!r} model={model!r}: {matches}")
        return matches[0]

    def close(self):
        try:
            self._jsdrv.unsubscribe(self._path + "/s/stats/value", self._stats_cb)
            self._jsdrv.publish(self._path + "/s/stats/ctrl", 0)
            self._jsdrv.close(self._path)
        finally:
            self._jsdrv.finalize()

    # -- statistics ---------------------------------------------------------

    def _configure_statistics(self):
        dev = self._path
        if self._model == "js110":
            self._jsdrv.publish(dev + "/s/i/range/select", "auto")
            # host-side statistics honor the requested frequency and report std
            self._jsdrv.publish(dev + "/s/i/ctrl", "on")
            self._jsdrv.publish(dev + "/s/v/ctrl", "on")
            self._jsdrv.publish(dev + "/s/p/ctrl", "on")
            base = 2_000_000  # JS110 host-side statistics sample rate
        else:  # js220, js320, ...
            self._jsdrv.publish(dev + "/s/i/range/mode", "auto")
            base = 1_000_000  # JS220/JS320 sensor-side statistics sample rate
        # The statistics update every scnt samples counted at the device's fixed
        # sample rate (``base``).  That rate is not reliably queryable across
        # models (``h/fs`` reads back ``None`` on the JS220/JS320), so use the
        # documented per-model value, matching pyjoulescope_driver's own
        # statistics example.
        scnt = max(1, int(round(base / self.frequency)))
        self._jsdrv.publish(dev + "/s/stats/scnt", scnt)
        self._jsdrv.publish(dev + "/s/stats/ctrl", 1)
        self._jsdrv.subscribe(dev + "/s/stats/value", "pub", self._stats_cb)

    def _on_statistics(self, topic, value):
        self._latest = value

    def _wait_for_statistics(self):
        """Block until a fresh statistics value arrives and return it."""
        self._latest = None
        deadline = time.monotonic() + max(2.0, 4.0 / self.frequency)
        while self._latest is None:
            if time.monotonic() > deadline:
                raise RuntimeError("timed out waiting for Joulescope statistics")
            time.sleep(0.01)
        return self._latest

    @staticmethod
    def _parse_statistics(value):
        signals = value["signals"]

        def signal(name):
            s = signals[name]
            return {k: (s[k]["value"] if k in s else None) for k in ("avg", "std", "min", "max")}

        return {
            "current": signal("current"),
            "voltage": signal("voltage"),
            "power": signal("power"),
            "charge_C": value["accumulators"]["charge"]["value"],
            "energy_J": value["accumulators"]["energy"]["value"],
            "time": {
                "utc": value["time"]["utc"]["value"],
                "samples": value["time"]["samples"]["value"],
            },
        }

    def get_statistics(self):
        return self._parse_statistics(self._wait_for_statistics())

    def start(self):
        value = self._wait_for_statistics()
        self._accum = {
            "charge": value["accumulators"]["charge"]["value"],
            "energy": value["accumulators"]["energy"]["value"],
            "utc": value["time"]["utc"]["value"][1],
        }

    def stop(self):
        if self._accum is None:
            raise RuntimeError("stop() called without a preceding start()")
        value = self._wait_for_statistics()
        time64 = self._pyjsdrv.time64
        utc_end = value["time"]["utc"]["value"][1]
        result = {
            "energy_J": value["accumulators"]["energy"]["value"] - self._accum["energy"],
            "charge_C": value["accumulators"]["charge"]["value"] - self._accum["charge"],
            "duration_s": time64.as_timestamp(utc_end) - time64.as_timestamp(self._accum["utc"]),
        }
        self._accum = None
        return result

    # -- sample capture -----------------------------------------------------

    def capture(self, filename, signals=None, duration=None, frequency=None):
        if duration is None:
            raise ValueError("capture() requires a duration in seconds")
        if frequency is not None:
            # Note: this changes the device sample rate for the rest of the
            # session; it is not restored to the default after the capture.
            self._jsdrv.publish(self._path + "/h/fs", int(frequency))
        recorder = self._pyjsdrv.Record(self._jsdrv, self._path, signals=signals or ["current", "voltage", "power"])
        recorder.open(filename)
        try:
            deadline = time.monotonic() + float(duration)
            while time.monotonic() < deadline:
                time.sleep(0.05)
        finally:
            recorder.close()
        return filename

    # -- power switch -------------------------------------------------------

    def set_power(self, enabled):
        dev = self._path
        value = "auto" if enabled else "off"
        # JS110 switches downstream power via the current range "select"; the
        # JS220 and JS320 use the current range "mode".
        topic = "/s/i/range/select" if self._model == "js110" else "/s/i/range/mode"
        self._jsdrv.publish(dev + topic, value)


_sessions = {}


def _key(serial, model):
    return f"{serial}/{model}"


def handle_open(serial, model, frequency):
    key = _key(serial, model)
    if key not in _sessions:
        _sessions[key] = JoulescopeSession(serial, model, frequency)
    # If a session for this device already exists it is reused as-is; the
    # frequency passed here is ignored (the existing session keeps its own).
    # handle_close() pops the session, so a fresh open() always reconfigures.
    return True


def handle_close(serial, model):
    session = _sessions.pop(_key(serial, model), None)
    if session is not None:
        session.close()


def handle_get_statistics(serial, model):
    return _sessions[_key(serial, model)].get_statistics()


def handle_start(serial, model):
    _sessions[_key(serial, model)].start()


def handle_stop(serial, model):
    return _sessions[_key(serial, model)].stop()


def handle_capture(serial, model, filename, signals=None, duration=None, frequency=None):
    return _sessions[_key(serial, model)].capture(filename, signals, duration, frequency)


def handle_set_power(serial, model, enabled):
    _sessions[_key(serial, model)].set_power(enabled)


def handle_remove(filename):
    with contextlib.suppress(FileNotFoundError):
        os.remove(filename)


methods = {
    "open": handle_open,
    "close": handle_close,
    "get_statistics": handle_get_statistics,
    "start": handle_start,
    "stop": handle_stop,
    "capture": handle_capture,
    "set_power": handle_set_power,
    "remove": handle_remove,
}
