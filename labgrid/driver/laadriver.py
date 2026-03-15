import os
import shutil
import tempfile
import time
from importlib import import_module
from urllib.parse import urlparse
from urllib.request import urlopen

import attr

from ..factory import target_factory
from ..protocol import ConsoleProtocol, PowerProtocol
from ..step import step
from .common import Driver
from .consoleexpectmixin import ConsoleExpectMixin
from .exception import ExecutionError
from .powerdriver import PowerResetMixin


def _get_laam():
    try:
        return import_module('laam')
    except ModuleNotFoundError:
        raise ModuleNotFoundError(
            "laam package not found, install labgrid[laa]"
        )


@target_factory.reg_driver
@attr.s(eq=False)
class LAASerialDriver(ConsoleExpectMixin, Driver, ConsoleProtocol):
    """Driver for serial console via LAA WebSocket bridge"""
    bindings = {"port": "LAASerialPort", }

    txdelay = attr.ib(default=0.0, validator=attr.validators.instance_of(float))
    timeout = attr.ib(default=3.0, validator=attr.validators.instance_of(float))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._laam = _get_laam()
        self._laa = None
        self._conn = None

    def on_activate(self):
        self._laa = self._laam.LAA(self.port.laa_identity)
        self._conn = self._laa.serials.connect_pexpect(self.port.serial_name)

    def on_deactivate(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        self._laa = None

    def _read(self, size: int = 1, timeout: float = 0.0, max_size: int = None):
        # ConnectPexpect.read_nonblocking() returns str, labgrid expects bytes
        data = self._conn.read_nonblocking(size, timeout)
        return data.encode("utf-8", errors="replace")

    def _write(self, data: bytes):
        return self._conn.send(data)


@target_factory.reg_driver
@attr.s(eq=False)
class LAAPowerDriver(Driver, PowerResetMixin, PowerProtocol):
    """Driver for DUT power control via LAA"""
    bindings = {"port": "LAAPowerPort", }

    delay = attr.ib(default=2.0, validator=attr.validators.instance_of(float))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._laam = _get_laam()
        self._laa = None

    def on_activate(self):
        self._laa = self._laam.LAA(self.port.laa_identity)

    def on_deactivate(self):
        self._laa = None

    def _execute_sequence(self, sequence):
        for vbus, state in sequence:
            try:
                self._laa.laacli.power(vbus, state)
            except self._laam.exceptions.LAAError as e:
                raise ExecutionError(
                    f"LAA power command failed ({vbus} {state}): {e}"
                ) from e

    @Driver.check_active
    @step()
    def on(self):
        self._execute_sequence(self.port.power_on)

    @Driver.check_active
    @step()
    def off(self):
        self._execute_sequence(self.port.power_off)

    @Driver.check_active
    @step()
    def cycle(self):
        if self.port.power_cycle is not None:
            self._execute_sequence(self.port.power_cycle)
        else:
            self.off()
            time.sleep(self.delay)
            self.on()


@target_factory.reg_driver
@attr.s(eq=False)
class LAAUSBGadgetMassStorageDriver(Driver):
    """Driver for USB gadget mass storage control via LAA"""
    bindings = {"port": "LAAUSBGadgetMassStorage", }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._laam = _get_laam()
        self._laa = None

    def on_activate(self):
        self._laa = self._laam.LAA(self.port.laa_identity)

    def on_deactivate(self):
        self._laa = None

    @Driver.check_active
    @step()
    def on(self):
        try:
            self._laa.laacli.usbg_ms("on", self.port.image)
        except self._laam.exceptions.LAAError as e:
            raise ExecutionError(f"LAA usbg-ms on failed: {e}") from e

    @Driver.check_active
    @step()
    def off(self):
        try:
            self._laa.laacli.usbg_ms("off", "")
        except self._laam.exceptions.LAAError as e:
            raise ExecutionError(f"LAA usbg-ms off failed: {e}") from e


@target_factory.reg_driver
@attr.s(eq=False)
class LAAUSBDriver(Driver):
    """Driver for USB port control via LAA"""
    bindings = {"port": "LAAUSBPort", }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._laam = _get_laam()
        self._laa = None

    def on_activate(self):
        self._laa = self._laam.LAA(self.port.laa_identity)

    def on_deactivate(self):
        self._laa = None

    @Driver.check_active
    @step()
    def on(self):
        for port in self.port.usb_ports:
            try:
                self._laa.laacli.usb(port, "on")
            except self._laam.exceptions.LAAError as e:
                raise ExecutionError(
                    f"LAA USB command failed (port {port} on): {e}"
                ) from e

    @Driver.check_active
    @step()
    def off(self):
        for port in self.port.usb_ports:
            try:
                self._laa.laacli.usb(port, "off")
            except self._laam.exceptions.LAAError as e:
                raise ExecutionError(
                    f"LAA USB command failed (port {port} off): {e}"
                ) from e


@target_factory.reg_driver
@attr.s(eq=False)
class LAAButtonDriver(Driver):
    """Driver for virtual button control via LAA"""
    bindings = {"port": "LAAButtonPort", }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._laam = _get_laam()
        self._laa = None

    def on_activate(self):
        self._laa = self._laam.LAA(self.port.laa_identity)

    def on_deactivate(self):
        self._laa = None

    @Driver.check_active
    @step()
    def press(self, button):
        if button not in self.port.buttons:
            raise ExecutionError(
                f"Button '{button}' not in resource buttons {self.port.buttons}"
            )
        try:
            self._laa.laacli.button(button, "on")
        except self._laam.exceptions.LAAError as e:
            raise ExecutionError(f"LAA button command failed ({button} on): {e}") from e

    @Driver.check_active
    @step()
    def release(self, button):
        if button not in self.port.buttons:
            raise ExecutionError(
                f"Button '{button}' not in resource buttons {self.port.buttons}"
            )
        try:
            self._laa.laacli.button(button, "off")
        except self._laam.exceptions.LAAError as e:
            raise ExecutionError(
                f"LAA button command failed ({button} off): {e}"
            ) from e


@target_factory.reg_driver
@attr.s(eq=False)
class LAALedDriver(Driver):
    """Driver for LED control via LAA"""
    bindings = {"port": "LAALed", }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._laam = _get_laam()
        self._laa = None

    def on_activate(self):
        self._laa = self._laam.LAA(self.port.laa_identity)

    def on_deactivate(self):
        self._laa = None

    @Driver.check_active
    @step()
    def on(self):
        try:
            self._laa.laacli.led("on")
        except self._laam.exceptions.LAAError as e:
            raise ExecutionError(f"LAA LED on failed: {e}") from e

    @Driver.check_active
    @step()
    def off(self):
        try:
            self._laa.laacli.led("off")
        except self._laam.exceptions.LAAError as e:
            raise ExecutionError(f"LAA LED off failed: {e}") from e


@target_factory.reg_driver
@attr.s(eq=False)
class LAATempDriver(Driver):
    """Driver for temperature sensor reading via LAA"""
    bindings = {"port": "LAATempSensor", }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._laam = _get_laam()
        self._laa = None

    def on_activate(self):
        self._laa = self._laam.LAA(self.port.laa_identity)

    def on_deactivate(self):
        self._laa = None

    @Driver.check_active
    @step()
    def get_temp(self, probe):
        try:
            return self._laa.laacli.temp(probe)
        except self._laam.exceptions.LAAError as e:
            raise ExecutionError(f"LAA temp command failed ({probe}): {e}") from e


@target_factory.reg_driver
@attr.s(eq=False)
class LAAWattDriver(Driver):
    """Driver for power measurement via LAA"""
    bindings = {"port": "LAAWattMeter", }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._laam = _get_laam()
        self._laa = None

    def on_activate(self):
        self._laa = self._laam.LAA(self.port.laa_identity)

    def on_deactivate(self):
        self._laa = None

    @Driver.check_active
    @step()
    def get_watts(self, vbus):
        try:
            return self._laa.laacli.watt(vbus)
        except self._laam.exceptions.LAAError as e:
            raise ExecutionError(f"LAA watt command failed ({vbus}): {e}") from e


@target_factory.reg_driver
@attr.s(eq=False)
class LAAProviderDriver(Driver):
    """Driver for uploading files to LAA file storage.

    Files are served via TFTP to the DUT. Source can be a local path
    or a URL."""
    bindings = {"provider": "LAAProvider", }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._laam = _get_laam()
        self._laa = None

    def on_activate(self):
        self._laa = self._laam.LAA(self.provider.laa_identity)

    def on_deactivate(self):
        self._laa = None

    @Driver.check_active
    @step(args=['source'], result=True)
    def stage(self, source):
        """Upload a file to the LAA. Source can be a local path or URL.

        Returns the filename as stored on the LAA."""
        is_url = source.startswith("http://") or source.startswith("https://")

        if is_url:
            name = os.path.basename(urlparse(source).path)
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp_path = tmp.name
            try:
                with urlopen(source) as r, open(tmp_path, "wb") as f:  # noqa: S310
                    shutil.copyfileobj(r, f)
                self._laa.files.push(name, tmp_path)
            finally:
                os.unlink(tmp_path)
        else:
            name = os.path.basename(source)
            if not os.path.exists(source):
                raise ExecutionError(f"file not found: {source}")
            self._laa.files.push(name, source)

        return name

    @Driver.check_active
    @step(result=True)
    def list(self):
        """Return list of files on the LAA."""
        return self._laa.files.list()

    @Driver.check_active
    @step(args=['name'])
    def remove(self, name):
        """Remove a file from the LAA."""
        try:
            self._laa.files.remove(name)
        except self._laam.exceptions.LAAError as e:
            raise ExecutionError(f"LAA file remove failed ({name}): {e}") from e
