# SPDX-License-Identifier: GPL-2.0-or-later
"""FTDI GPIO driver using a labgrid agent."""

import threading

import attr

from ..factory import target_factory
from ..protocol import DigitalOutputProtocol
from ..resource.remote import NetworkFTDIGPIO
from ..step import step
from ..util.agentwrapper import AgentWrapper
from .common import Driver

# Pins on one interface must share the agent's whole-bus direction state. The
# lock protects only this client-side lifecycle bookkeeping; agent requests are
# handled synchronously by the agent process.
_shared_agents = {}
_shared_lock = threading.Lock()


def _acquire_agent(host, busnum, devnum, interface):
    key = (host, busnum, devnum, interface)
    with _shared_lock:
        entry = _shared_agents.get(key)
        if entry is None:
            wrapper = AgentWrapper(host)
            proxy = wrapper.load("ftdigpio")
            entry = {"wrapper": wrapper, "proxy": proxy, "refs": 0}
            _shared_agents[key] = entry
        entry["refs"] += 1
        return entry["proxy"]


def _release_agent(host, busnum, devnum, interface):
    key = (host, busnum, devnum, interface)
    with _shared_lock:
        entry = _shared_agents.get(key)
        if entry is None:
            return
        entry["refs"] -= 1
        if entry["refs"] <= 0:
            del _shared_agents[key]
            entry["wrapper"].close()


@target_factory.reg_driver
@attr.s(eq=False)
class FTDIGPIODriver(Driver, DigitalOutputProtocol):
    """Control one FTDI data-bus GPIO line through a labgrid agent."""

    bindings = {
        "gpio": {"FTDIGPIO", NetworkFTDIGPIO},
    }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._proxy = None
        self._host = None

    def on_activate(self):
        self._host = self.gpio.host if isinstance(self.gpio, NetworkFTDIGPIO) else None
        proxy = _acquire_agent(self._host, self.gpio.busnum, self.gpio.devnum, self.gpio.interface)
        # Program this line's direction from the resource config before any
        # read/write. Bit-bang mode is whole-port, so the agent keeps the union
        # of the configured output lines per interface.
        try:
            proxy.setup(
                self.gpio.vendor_id,
                self.gpio.model_id,
                self.gpio.busnum,
                self.gpio.devnum,
                self.gpio.interface,
                self.gpio.index,
                self.gpio.direction == "out",
            )
        except Exception:
            _release_agent(self._host, self.gpio.busnum, self.gpio.devnum, self.gpio.interface)
            self._host = None
            raise
        self._proxy = proxy

    def on_deactivate(self):
        self._proxy = None
        _release_agent(self._host, self.gpio.busnum, self.gpio.devnum, self.gpio.interface)
        self._host = None

    @Driver.check_active
    @step(result=True)
    def get(self):
        status = self._proxy.get(
            self.gpio.vendor_id,
            self.gpio.model_id,
            self.gpio.busnum,
            self.gpio.devnum,
            self.gpio.interface,
            self.gpio.index,
        )
        if self.gpio.invert:
            status = not status
        return status

    @Driver.check_active
    @step(args=["status"])
    def set(self, status):
        if self.gpio.invert:
            status = not status
        self._proxy.set(
            self.gpio.vendor_id,
            self.gpio.model_id,
            self.gpio.busnum,
            self.gpio.devnum,
            self.gpio.interface,
            self.gpio.index,
            status,
        )
