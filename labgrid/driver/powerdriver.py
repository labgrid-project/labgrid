import shlex
import time
import math
from importlib import import_module

import attr

from ..factory import target_factory
from ..protocol import PowerProtocol, DigitalOutputProtocol, ResetProtocol
from ..resource import NetworkPowerPort
from ..step import step
from ..util.proxy import proxymanager
from ..util.helper import processwrapper
from .common import Driver
from .exception import ExecutionError


@attr.s(eq=False)
class PowerResetMixin(ResetProtocol):
    """
    ResetMixin implements the ResetProtocol for drivers which support the PowerProtocol
    """
    priorities = {ResetProtocol: -10}

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    @Driver.check_active
    @step()
    def reset(self):
        self.cycle()

@target_factory.reg_driver
@attr.s(eq=False)
class ManualPowerDriver(Driver, PowerResetMixin, PowerProtocol):
    """ManualPowerDriver - Driver to tell the user to control a target's power"""

    @Driver.check_active
    @step()
    def on(self):
        self.target.interact(
            f"Turn the target {self.target.name} ON and press enter"
        )

    @Driver.check_active
    @step()
    def off(self):
        self.target.interact(
            f"Turn the target {self.target.name} OFF and press enter"
        )

    @Driver.check_active
    @step()
    def cycle(self):
        self.target.interact(
            f"CYCLE the target {self.target.name} and press enter"
        )


@target_factory.reg_driver
@attr.s(eq=False)
class SiSPMPowerDriver(Driver, PowerResetMixin, PowerProtocol):
    """SiSPMPowerDriver - Driver using a SiS-PM (Silver Shield PM) to control a
       target's power using the sispmctl tool - http://sispmctl.sourceforge.net/"""

    bindings = {"port": {"SiSPMPowerPort", "NetworkSiSPMPowerPort"}, }
    delay = attr.ib(default=2.0, validator=attr.validators.instance_of(float))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.target.env:
            self.tool = self.target.env.config.get_tool('sispmctl') or 'sispmctl'
        else:
            self.tool = 'sispmctl'

    def _get_sispmctl_prefix(self):
        return self.port.command_prefix + [
            self.tool,
            "-U", f"{self.port.busnum:03d}:{self.port.devnum:03d}",
        ]

    @Driver.check_active
    @step()
    def on(self):
        cmd = ['-o', str(self.port.index)]
        processwrapper.check_output(self._get_sispmctl_prefix() + cmd)

    @Driver.check_active
    @step()
    def off(self):
        cmd = ['-f', str(self.port.index)]
        processwrapper.check_output(self._get_sispmctl_prefix() + cmd)

    @Driver.check_active
    @step()
    def cycle(self):
        self.off()
        time.sleep(self.delay)
        self.on()

    @Driver.check_active
    @step()
    def get(self):
        cmd = ['-q', '-g', str(self.port.index)]
        output = processwrapper.check_output(self._get_sispmctl_prefix() + cmd)
        if output.strip() == b"on":
            return True
        if output.strip() == b"off":
            return False
        raise ExecutionError(f"Did not find port status in sispmctl output ({repr(output)})")


@target_factory.reg_driver
@attr.s(eq=False)
class ExternalPowerDriver(Driver, PowerResetMixin, PowerProtocol):
    """ExternalPowerDriver - Driver using an external command to control a target's power"""
    cmd_on = attr.ib(validator=attr.validators.instance_of(str))
    cmd_off = attr.ib(validator=attr.validators.instance_of(str))
    cmd_cycle = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str))
    )
    delay = attr.ib(default=2.0, validator=attr.validators.instance_of(float))

    @Driver.check_active
    @step()
    def on(self):
        cmd = shlex.split(self.cmd_on)
        processwrapper.check_output(cmd)

    @Driver.check_active
    @step()
    def off(self):
        cmd = shlex.split(self.cmd_off)
        processwrapper.check_output(cmd)

    @Driver.check_active
    @step()
    def cycle(self):
        if self.cmd_cycle is not None:
            cmd = shlex.split(self.cmd_cycle)
            processwrapper.check_output(cmd)
        else:
            self.off()
            time.sleep(self.delay)
            self.on()

@target_factory.reg_driver
@attr.s(eq=False)
class NetworkPowerDriver(Driver, PowerResetMixin, PowerProtocol):
    """NetworkPowerDriver - Driver using a networked power switch to control a target's power"""
    bindings = {"port": NetworkPowerPort, }
    delay = attr.ib(default=2.0, validator=attr.validators.instance_of(float))


    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        # TODO: allow backends to register models with other names
        self.backend = import_module(
            f".power.{self.port.model}",
            __package__
        )
        self._host = None
        self._port = None

    def on_activate(self):
        # we can only forward if the backend knows which port to use
        backend_port = getattr(self.backend, 'PORT', None)
        if backend_port:
            self._host, self._port = proxymanager.get_host_and_port(
                self.port, force_port=backend_port
            )
        else:
            self._host = self.port.host
            self._port = None

    @Driver.check_active
    @step()
    def on(self):
        self.backend.power_set(self._host, self._port, self.port.index, True)

    @Driver.check_active
    @step()
    def off(self):
        self.backend.power_set(self._host, self._port, self.port.index, False)

    @Driver.check_active
    @step()
    def cycle(self):
        self.off()
        time.sleep(self.delay)
        self.on()

    @Driver.check_active
    def get(self):
        return self.backend.power_get(self._host, self._port, self.port.index)

@target_factory.reg_driver
@attr.s(eq=False)
class DigitalOutputPowerDriver(Driver, PowerResetMixin, PowerProtocol):
    """
    DigitalOutputPowerDriver uses a DigitalOutput to control the power
    of a DUT.
    """
    bindings = {"output": DigitalOutputProtocol, }
    delay = attr.ib(default=1.0, validator=attr.validators.instance_of(float))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    @Driver.check_active
    @step()
    def on(self):
        self.output.set(True)

    @Driver.check_active
    @step()
    def off(self):
        self.output.set(False)

    @Driver.check_active
    @step()
    def cycle(self):
        self.off()
        time.sleep(self.delay)
        self.on()

    @Driver.check_active
    @step()
    def get(self):
        return self.output.get()

@target_factory.reg_driver
@attr.s(eq=False)
class YKUSHPowerDriver(Driver, PowerResetMixin, PowerProtocol):
    """YKUSHPowerDriver - Driver using a YEPKIT YKUSH switchable USB hub
        to control a target's power - https://www.yepkit.com/products/ykush"""
    bindings = {"port": "YKUSHPowerPort", }
    delay = attr.ib(default=2.0, validator=attr.validators.instance_of(float))


    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        # uses the YKUSH pykush interface from here:
        # https://github.com/Yepkit/pykush
        self.pykush_mod = import_module('pykush.pykush')
        self.pykush = self.pykush_mod.YKUSH(serial=self.port.serial)

    @Driver.check_active
    @step()
    def on(self):
        self.pykush.set_port_state(self.port.index, self.pykush_mod.YKUSH_PORT_STATE_UP)

    @Driver.check_active
    @step()
    def off(self):
        self.pykush.set_port_state(self.port.index, self.pykush_mod.YKUSH_PORT_STATE_DOWN)

    @Driver.check_active
    @step()
    def cycle(self):
        self.off()
        time.sleep(self.delay)
        self.on()

    @Driver.check_active
    def get(self):
        return self.pykush.get_port_state(self.port.index)

@target_factory.reg_driver
@attr.s(eq=False)
class USBPowerDriver(Driver, PowerResetMixin, PowerProtocol):
    """USBPowerDriver - Driver using a power switchable USB hub and the uhubctl
    tool (https://github.com/mvp/uhubctl) to control a target's power"""

    bindings = {"hub": {"USBPowerPort", "NetworkUSBPowerPort"}, }
    delay = attr.ib(default=2.0, validator=attr.validators.instance_of(float))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.target.env:
            self.tool = self.target.env.config.get_tool('uhubctl') or 'uhubctl'
        else:
            self.tool = 'uhubctl'

    def _switch(self, cmd):
        cmd = self.hub.command_prefix + [
            self.tool,
            "-l", self.hub.path,
            "-p", str(self.hub.index),
            "-r", "100", # use 100 retries for now
            "-a", cmd,
        ]
        processwrapper.check_output(cmd)

    @Driver.check_active
    @step()
    def on(self):
        self._switch("on")

    @Driver.check_active
    @step()
    def off(self):
        self._switch("off")

    @Driver.check_active
    @step()
    def cycle(self):
        self.off()
        time.sleep(self.delay)
        self.on()

    @Driver.check_active
    def get(self):
        cmd = self.hub.command_prefix + [
            self.tool,
            "-l", self.hub.path,
            "-p", str(self.hub.index),
        ]
        output = processwrapper.check_output(cmd)
        for line in output.splitlines():
            if not line or not line.startswith(b' '):
                continue
            prefix, status = line.strip().split(b':', 1)
            if not prefix == b"Port %d" % self.hub.index:
                continue
            status = status.split()
            if b"power" in status:
                return True
            if b"off" in status:
                return False
        raise ExecutionError(f"Did not find port status in uhubctl output ({repr(output)})")


@target_factory.reg_driver
@attr.s(eq=False)
class PDUDaemonDriver(Driver, PowerResetMixin, PowerProtocol):
    """PDUDaemonDriver - Driver using a PDU port available via pdudaemon"""
    bindings = {"port": "PDUDaemonPort", }
    delay = attr.ib(default=5.0, validator=attr.validators.instance_of(float))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._requests = import_module('requests')
        self._host = None
        self._port = None

    def _build_url(self, cmd):
        res = f"http://{self._host}:{self._port}/power/control/{cmd}?hostname={self.port.pdu}&port={self.port.index}"  # pylint: disable=line-too-long
        if cmd == 'reboot':
            res += f"&delay={math.ceil(self.delay)}"
        return res

    def on_activate(self):
        self._host, self._port = proxymanager.get_host_and_port(self.port, default_port=16421)

    @Driver.check_active
    @step()
    def on(self):
        r = self._requests.get(self._build_url('on'))
        r.raise_for_status()
        time.sleep(1)  # give pdudaemon some time to execute the request

    @Driver.check_active
    @step()
    def off(self):
        r = self._requests.get(self._build_url('off'))
        r.raise_for_status()
        time.sleep(1)  # give pdudaemon some time to execute the request

    @Driver.check_active
    @step()
    def cycle(self):
        r = self._requests.get(self._build_url('reboot'))
        r.raise_for_status()
        time.sleep(self.delay + 1)  # give pdudaemon some time to execute the request

    @Driver.check_active
    def get(self):
        return None
