# SPDX-License-Identifier: GPL-2.0-or-later
"""FTDI GPIO driver using a labgrid agent."""

import threading

import attr

from ..factory import target_factory
from ..protocol import DigitalOutputProtocol
from ..resource.remote import NetworkFTDIGPIO, RemoteUSBResource
from ..step import step
from ..util.agentwrapper import AgentWrapper
from .common import Driver

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
            try:
                entry["proxy"].close()
            finally:
                entry["wrapper"].close()


@target_factory.reg_driver
@attr.s(eq=False)
class FTDIGPIODriver(Driver, DigitalOutputProtocol):
    """Control one FTDI data-bus GPIO line through a labgrid agent."""

    bindings = {
        "gpio": {"FTDIGPIO", NetworkFTDIGPIO},
        "networkservice": {"NetworkService", None},
    }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._proxy = None
        self._host = None

    def on_activate(self):
        self._host = self.gpio.host if isinstance(self.gpio, RemoteUSBResource) else None
        if self.networkservice and self.networkservice.address == self._host:
            self._host = f"{self.networkservice.username}@{self._host}"
        self._proxy = _acquire_agent(self._host, self.gpio.busnum, self.gpio.devnum, self.gpio.interface)

    def on_deactivate(self):
        self._proxy = None
        _release_agent(self._host, self.gpio.busnum, self.gpio.devnum, self.gpio.interface)
        self._host = None

    @Driver.check_active
    @step(result=True)
    def get(self):
        status = bool(self._proxy.get(
            self.gpio.vendor_id,
            self.gpio.model_id,
            self.gpio.busnum,
            self.gpio.devnum,
            self.gpio.interface,
            self.gpio.index,
        ))
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
            bool(status),
        )
