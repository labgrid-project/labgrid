import attr

from ..factory import target_factory
from ..resource.pyvisa import NetworkPyVISADevice
from ..util.agentwrapper import AgentWrapper
from .common import Driver

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
    def command(self, cmd, timeout=2000):
        """
        Sent the specified command to the instrument.

        Args:
            cmd (str): command to be executed
            timeout (int): optional, I/O operation timeout in ms, default is 2000ms
        """
        self.proxy.write(self.device_identifier, self.pyvisa_resource.backend, cmd, timeout)

    @Driver.check_active
    def query(self, cmd, timeout=2000):
        """
        Sent the specified command to the instrument and read the response.

        Args:
            cmd (str): command to be executed
            timeout (int): optional, I/O operation timeout in ms, default is 2000ms

        Returns:
            str: response from the instrument, with possible termination removed.
        """
        return self.proxy.query(self.device_identifier, self.pyvisa_resource.backend, cmd, timeout).rstrip()

    @Driver.check_active
    def query_iterable(self, cmd, timeout=2000, **kwargs):
        """
        Sent the specified command to the instrument and read the response.

        Args:
            cmd (str): command to be executed
            timeout (int): optional, I/O operation timeout in ms, default is 2000ms

        Returns:
            List[float]: response from the instrument, retunring list of float values (readings).
        """
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
        """
        Sent the identify command to the instrument and read the response.

        Returns:
            str: returns a comma-separated string with the information about the instrument (manufacturer, model, serial number, firmware version).
        """
        return self.query("*IDN?")
