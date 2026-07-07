import os
import time
import uuid

import attr

from ..factory import target_factory
from ..protocol import EnergyAnalyzerProtocol, PowerProtocol
from ..resource.joulescope import JoulescopeDevice
from ..resource.remote import NetworkJoulescopeDevice
from ..step import step
from ..util.agentwrapper import AgentWrapper
from ..util.ssh import sshmanager
from .common import Driver


@target_factory.reg_driver
@attr.s(eq=False)
class JoulescopeDriver(Driver, EnergyAnalyzerProtocol, PowerProtocol):
    """The JoulescopeDriver controls a Joulescope energy analyzer.

    It wraps ``pyjoulescope_driver`` to stream measurement statistics
    (current, voltage, power and accumulated charge/energy), to capture
    high-rate samples to a JLS file, and to connect/disconnect the device
    current path (downstream power) as a :class:`PowerProtocol` power switch.

    ``pyjoulescope_driver`` runs on the host the Joulescope is attached to
    through labgrid's agent mechanism, so the same driver works for a locally
    attached device and for one shared over the distributed infrastructure via
    a :class:`~labgrid.resource.remote.NetworkJoulescopeDevice`.  Only the host
    with the device attached needs the ``joulescope`` extra installed.

    Power switching (``on``/``off``/``cycle``) controls downstream power to the
    device under test: the JS110 uses the current range ``select`` and the JS220
    and JS320 use the current range ``mode``.

    Args:
        frequency (float): statistics update frequency in Hz
        delay (float): delay between off and on during a power cycle
    """

    bindings = {"device": {JoulescopeDevice, NetworkJoulescopeDevice}}
    frequency = attr.ib(default=2.0, validator=attr.validators.instance_of(float))
    delay = attr.ib(default=2.0, validator=attr.validators.instance_of(float))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.wrapper = None
        self.proxy = None

    # -- life cycle ---------------------------------------------------------

    def on_activate(self):
        host = self.device.host if isinstance(self.device, NetworkJoulescopeDevice) else None
        self.wrapper = AgentWrapper(host)
        try:
            self.proxy = self.wrapper.load("joulescope")
            self.proxy.open(self.device.serial, self.device.model, self.frequency)
        except Exception:
            # on_deactivate() only runs once the driver is active, so clean up
            # the (possibly remote) agent subprocess if opening the device fails.
            self.wrapper.close()
            self.wrapper = None
            self.proxy = None
            raise

    def on_deactivate(self):
        try:
            self.proxy.close(self.device.serial, self.device.model)
        finally:
            self.wrapper.close()
            self.wrapper = None
            self.proxy = None

    # -- statistics ---------------------------------------------------------

    @Driver.check_active
    @step(result=True)
    def get_statistics(self):
        return self.proxy.get_statistics(self.device.serial, self.device.model)

    @Driver.check_active
    @step()
    def start(self):
        self.proxy.start(self.device.serial, self.device.model)

    @Driver.check_active
    @step(result=True)
    def stop(self):
        return self.proxy.stop(self.device.serial, self.device.model)

    # -- sample capture -----------------------------------------------------

    @Driver.check_active
    @step(args=["filename", "duration"])
    def capture(self, filename, signals=None, duration=None, frequency=None):
        if duration is None:
            raise ValueError("capture() requires a duration in seconds")
        if isinstance(self.device, NetworkJoulescopeDevice):
            # Record on the host the device is attached to, then copy the JLS
            # file back to the client and remove the remote copy.
            remote = f"/tmp/labgrid-joulescope-{uuid.uuid4()}.jls"
            self.proxy.capture(self.device.serial, self.device.model, remote, signals, duration, frequency)
            try:
                sshmanager.get_file(self.device.host, remote, filename)
            finally:
                self.proxy.remove(remote)
        else:
            self.proxy.capture(
                self.device.serial, self.device.model, os.fspath(filename), signals, duration, frequency
            )

    # -- power switch (PowerProtocol) --------------------------------------

    @Driver.check_active
    @step()
    def on(self):
        self.proxy.set_power(self.device.serial, self.device.model, True)

    @Driver.check_active
    @step()
    def off(self):
        self.proxy.set_power(self.device.serial, self.device.model, False)

    @Driver.check_active
    @step()
    def cycle(self):
        self.off()
        time.sleep(self.delay)
        self.on()
