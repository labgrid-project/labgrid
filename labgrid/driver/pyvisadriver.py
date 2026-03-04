import attr

from ..factory import target_factory
from ..resource.pyvisa import NetworkPyVISADevice
from ..util.agentwrapper import AgentWrapper
from .common import Driver

TIMEOUT_DEFAULT = 2000  # Default timeout for visa operations in ms

@target_factory.reg_driver
@attr.s(eq=False)
class PyVISADriver(Driver):
    """The PyVISADriver provides a transparent layer to the PyVISA module allowing to get a pyvisa resource

    Args:
        bindings (dict): driver to use with PyVISA
    """
    bindings = {"pyvisa_resource": {"PyVISADevice", "NetworkPyVISADevice"}}

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.wrapper = None

    def on_activate(self):
        url = "" if self.pyvisa_resource.url == "" else f"::{self.pyvisa_resource.url}"
        self.device_identifier = f"{self.pyvisa_resource.type}{url}::{self.pyvisa_resource.resource}"
        if isinstance(self.pyvisa_resource, NetworkPyVISADevice):
            host = self.pyvisa_resource.host
        else:
            host = None
        self.wrapper = AgentWrapper(host)
        self.proxy = self.wrapper.load("visa_instrument")

    def on_deactivate(self):
        self.wrapper.close()
        self.wrapper = None

    @Driver.check_active
    def get_session(self):
        raise NotImplementedError('Deprecated, use command or query instead')

    @Driver.check_active
    def command(self, cmd, timeout=TIMEOUT_DEFAULT):
        self.proxy.write(self.device_identifier, self.pyvisa_resource.backend, cmd, timeout)

    @Driver.check_active
    def query(self, cmd, timeout=TIMEOUT_DEFAULT):
        return self.proxy.query(self.device_identifier, self.pyvisa_resource.backend, cmd, timeout).rstrip()

    @Driver.check_active
    def query_iterable(self, cmd, timeout=TIMEOUT_DEFAULT, **kwargs):
        return self.proxy.query(
            self.device_identifier,
            self.pyvisa_resource.backend,
            cmd,
            timeout,
            iterable=True,
            is_ascii=True,
            **kwargs
        )

    @Driver.check_active
    def identify(self):
        return self.query("*IDN?")
