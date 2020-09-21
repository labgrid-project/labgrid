import shlex
import time
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
            ".power.{}".format(self.port.model),
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
        raise ExecutionError("Did not find port status in uhubctl output ({})".format(repr(output)))


@target_factory.reg_driver
@attr.s(eq=False)
class PDUDaemonDriver(Driver, PowerResetMixin, PowerProtocol):
    """PDUDaemonDriver - Driver using a PDU port available via pdudaemon"""
    bindings = {"port": "PDUDaemonPort", }
    delay = attr.ib(default=5, validator=attr.validators.instance_of(int))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._requests = import_module('requests')
        self._host = None
        self._port = None

    def _build_url(self, cmd):
        res = "http://{}:{}/power/control/{}?hostname={}&port={}".format(
            self._host, self._port, cmd, self.port.pdu, self.port.index)
        if cmd == 'reboot':
            res += "&delay={}".format(self.delay)
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


@target_factory.reg_driver
@attr.s(eq=False)
class USBRelayPowerDriver(Driver, PowerResetMixin, PowerProtocol):
    """USBRelayPowerDriver - Driver using a power switchable usbrelay and the `usbrelay`
    tool (https://github.com/darrylb123/usbrelay) to control a target's power"""

    bindings = {"relay": {"USBRelay"},}
    delay = attr.ib(default=2.0, validator=attr.validators.instance_of(float))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.target.env:
            self.tool = self.target.env.config.get_tool('usbrelay') or 'usbrelay'
        else:
            self.tool = 'usbrelay'

    def _switch(self, cmd):

        number_command = "1" if cmd.lower() == "on" else "0"

        cmd = self.relay.command_prefix + [
            self.tool,
            "{}_{}={}".format(self.relay.name, self.relay.index, number_command)
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
        cmd = self.relay.command_prefix + [
            self.tool,
            self.relay.name
        ]
        output = processwrapper.check_output(cmd)
        for line in output.splitlines():
            if not line:
                continue
            prefix, status = line.strip().split(b'=', 1)
            if not self.relay.name in str(prefix):
                continue
            status = status.split()
            if b"1" in status:
                return True
            if b"0" in status:
                return False
        raise ExecutionError("Did not find relay status in usbrelay output ({})".format(repr(output)))