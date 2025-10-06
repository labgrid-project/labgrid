import inspect
import logging
from importlib import import_module
from time import sleep

import attr

from ..factory import target_factory
from ..protocol import PowerProtocol
from ..step import step
from .common import Driver
from .powerdriver import PowerResetMixin


@target_factory.reg_driver
@attr.s(eq=False)
class TMInstrument(Driver):
    """
    This driver provides a common interface for TMC SCPI compatible instruments.

    Args:
        bindings (dict): driver to use with test and measurement instrument

    TODO: Create a common base abstract (aka protocol) class for VISA based instruments
    """

    bindings = {"inst": {"PyVISADriver", "USBTMCDriver"}}

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._backend = None
        # Mapping of known instruments to their backend module
        self.instruments_backend = {
        }

    @Driver.check_active
    def command(self, cmd):
        self.inst.command(cmd)

    @Driver.check_active
    def query(self, cmd):
        return self.inst.query(cmd)

    @Driver.check_active
    def query_iterable(self, cmd, **kwargs):
        if hasattr(self.inst, "query_iterable"):
            return self.inst.query_iterable(cmd, **kwargs)
        else:
            raise NotImplementedError("query_iterable not implemented in underlying driver")

    @Driver.check_active
    def identify(self):
        return self.inst.identify()

    @Driver.check_active
    def clear_status(self):
        self.inst.command("*CLS")

    @Driver.check_active
    def reset_device(self):
        self.inst.command("*RST")

    @Driver.check_active
    def operation_complete(self):
        self.inst.command("*OPC")

    @Driver.check_active
    def is_operation_complete(self):
        return self.inst.query("*OPC?")

    @Driver.check_active
    def wait_to_continue(self):
        self.inst.command("*WAI")

    @property
    def _backend_get(self):
        if self._backend is None:
            model = self.identify()
            for key, value in self.instruments_backend.items():
                if key in model:
                    self._backend = import_module(value, __package__)
                    break
        return self._backend

    @Driver.check_active
    @step(args=["cmd", "args"])
    def backend(self, cmd=None, args=[]):
        self._backend = self._backend_get
        if self._backend is None:  # Backend is not specified
            return []
        elif cmd is None:  # No command = return the list of implemented
            functions = []
            for name, func in inspect.getmembers(self._backend, inspect.isfunction):
                if inspect.getmodule(func) == self._backend:
                    functions.append([name, str(inspect.signature(func))])
            return functions
        else:  # Execute command from backend
            if hasattr(self._backend, cmd):
                func = getattr(self._backend, cmd)
                return func(self, *args)
            else:
                raise ValueError(f"Unknown backend command: {cmd}")


@target_factory.reg_driver
@attr.s(eq=False)
class TMInstrumentPower(TMInstrument, PowerResetMixin, PowerProtocol):
    """
    This driver provides a common interface for TMC SCPI compatible instruments with PowerProtocol API.

    Args:
        bindings (dict): driver to use with test and measurement instrument
    """

    bindings = TMInstrument.bindings

    delay = attr.ib(
        default=3.0, converter=attr.converters.optional(float), validator=attr.validators.instance_of(float)
    )
    max_voltage = attr.ib(
        default=None,
        converter=attr.converters.optional(float),
        validator=attr.validators.optional(attr.validators.instance_of(float)),
    )
    max_current = attr.ib(
        default=None,
        converter=attr.converters.optional(float),
        validator=attr.validators.optional(attr.validators.instance_of(float)),
    )

    @Driver.check_active
    @step()
    def on(self):
        self.backend("activate", args=[1, self.inst.index])

    @Driver.check_active
    @step()
    def off(self):
        self.backend("activate", args=[0, self.inst.index])

    @Driver.check_active
    @step()
    def cycle(self):
        self.off()
        sleep(self.delay)
        self.on()

    @Driver.check_active
    @step(args=["value"])  # only for StrategyExecutor
    def set_voltage_target(self, value=None):
        if self.max_voltage is not None and value > self.max_voltage:
            raise ValueError(
                "Requested voltage target({}) is higher than configured maximum ({})".format(value, self.max_voltage)
            )  # pylint: disable=line-too-long
        self.backend("voltage_set", args=[value, self.inst.index])
        logging.info(f"Target voltage set to {value} V")

    @Driver.check_active
    @step()
    def get_voltage_target(self):
        v = self.backend("voltage_get", args=[self.inst.index])
        return v

    @Driver.check_active
    @step(args=["value"])
    def set_current_limit(self, value):
        if self.max_current is not None and value > self.max_current:
            raise ValueError(
                "Requested current limit ({}) is higher than configured maximum ({})".format(value, self.max_current)
            )  # pylint: disable=line-too-long
        self.backend("current_set", args=[value, self.inst.index])
        logging.info(f"Current limit set to {value} A")

    @Driver.check_active
    @step()
    def get_current_target(self):
        c = self.backend("current_get", args=[self.inst.index])
        return c

    @Driver.check_active
    @step()
    def get_voltage_preset(self):
        v = self.backend("voltage_preset_get", args=[self.inst.index])
        return v

    @Driver.check_active
    @step()
    def get_current_preset(self):
        c = self.backend("current_preset_get", args=[self.inst.index])
        return c

    @Driver.check_active
    @step()
    def get(self):
        state = self.backend("state_get", args=[self.inst.index])
        state = True if "ON" in state else False
        return state
