import shlex
import subprocess
import time
from importlib import import_module

import attr

from ..factory import target_factory
from ..protocol import PowerProtocol, DigitalOutputProtocol, ResetProtocol
from ..resource import NetworkPowerPort
from ..resource import YKUSHPowerPort
from ..resource.remote import NetworkUSBPowerPort
from ..resource.udev import USBPowerPort
from ..step import step
from .common import Driver
from .exception import ExecutionError


@attr.s(cmp=False)
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
@attr.s(cmp=False)
class ManualPowerDriver(Driver, PowerResetMixin, PowerProtocol):
    """ManualPowerDriver - Driver to tell the user to control a target's power"""

    @Driver.check_active
    @step()
    def on(self):
        self.target.interact(
            "Turn the target {name} ON and press enter".format(name=self.name)
        )

    @Driver.check_active
    @step()
    def off(self):
        self.target.interact(
            "Turn the target {name} OFF and press enter".
            format(name=self.name)
        )

    @Driver.check_active
    @step()
    def cycle(self):
        self.target.interact(
            "CYCLE the target {name} and press enter".format(name=self.name)
        )


@target_factory.reg_driver
@attr.s(cmp=False)
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
        subprocess.check_call(cmd)

    @Driver.check_active
    @step()
    def off(self):
        cmd = shlex.split(self.cmd_off)
        subprocess.check_call(cmd)

    @Driver.check_active
    @step()
    def cycle(self):
        if self.cmd_cycle is not None:
            cmd = shlex.split(self.cmd_cycle)
            subprocess.check_call(cmd)
        else:
            self.off()
            time.sleep(self.delay)
            self.on()

@target_factory.reg_driver
@attr.s(cmp=False)
class NetworkPowerDriver(Driver, PowerResetMixin, PowerProtocol):
    """NetworkPowerDriver - Driver using a networked power switch to control a target's power"""
    bindings = {"port": NetworkPowerPort, }
    delay = attr.ib(default=2.0, validator=attr.validators.instance_of(float))


    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        # TODO: allow backends to register models with other names
        self.backend = import_module(
            ".power.{}".format(self.port.model),
            __package__
        )

    @Driver.check_active
    @step()
    def on(self):
        self.backend.power_set(self.port.host, self.port.index, True)

    @Driver.check_active
    @step()
    def off(self):
        self.backend.power_set(self.port.host, self.port.index, False)

    @Driver.check_active
    @step()
    def cycle(self):
        self.off()
        time.sleep(self.delay)
        self.on()

    @Driver.check_active
    def get(self):
        return self.backend.power_get(self.port.host, self.port.index)

@target_factory.reg_driver
@attr.s(cmp=False)
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
@attr.s(cmp=False)
class YKUSHPowerDriver(Driver, PowerResetMixin, PowerProtocol):
    """YKUSHPowerDriver - Driver using a YEPKIT YKUSH switchable USB hub
        to control a target's power - https://www.yepkit.com/products/ykush"""
    bindings = {"port": YKUSHPowerPort, }
    delay = attr.ib(default=2.0, validator=attr.validators.instance_of(float))


    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        # uses the YKUSH pykush interface from here:
        # https://github.com/Yepkit/pykush
        self.pykush_mod = import_module('pykush')
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
@attr.s(cmp=False)
class USBPowerDriver(Driver, PowerResetMixin, PowerProtocol):
    """USBPowerDriver - Driver using a power switchable USB hub and the uhubctl
    tool (https://github.com/mvp/uhubctl) to control a target's power"""

    bindings = {"hub": {USBPowerPort, NetworkUSBPowerPort}, }
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
        subprocess.check_call(cmd)

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
        output = subprocess.check_output(cmd)
        for line in output.splitlines():
            if not line or not line.startswith(b' '):
                continue
            prefix, status = line.strip().split(b':', 1)
            if not prefix == b"Port %d" % self.hub.index:
                continue
            status = status.split()
            if b"power" in status:
                return True
            elif b"off" in status:
                return False
        raise ExecutionError("Did not find port status in uhubctl output ({})".format(repr(output)))
