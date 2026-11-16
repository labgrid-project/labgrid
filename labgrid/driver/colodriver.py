"""CoLo firmware support for Cobalt microservers."""
import attr

from ..factory import target_factory
from ..step import step
from .common import Driver
from .consolebootdriver import ConsoleBootDriver


@target_factory.reg_driver
@attr.s(eq=False)
class CoLoDriver(ConsoleBootDriver):
    """Control the CoLo boot menu and command interpreter.

    Bind to a console implementing ConsoleProtocol. The firmware driver remains
    independent of the underlying console transport.
    """
    prompt = attr.ib(default=r'(?m)^> ', validator=attr.validators.instance_of(str))
    autoboot = attr.ib(default='boot: running boot menu', validator=attr.validators.instance_of(str))
    boot_command = attr.ib(default='exec', validator=attr.validators.instance_of(str))

    @Driver.check_active
    @step(args=['server', 'filename'])
    def load(self, server, filename, timeout=120):
        """Initialize networking and load a file using CoLo's TFTP command."""
        self._execute('net', timeout=timeout)
        return self._execute(f'tftp {server} {filename}', timeout=timeout)
