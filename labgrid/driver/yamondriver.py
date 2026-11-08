"""MIPS YAMON firmware console support."""
import attr

from ..factory import target_factory
from ..step import step
from .common import Driver
from .consolebootdriver import ConsoleBootDriver


@target_factory.reg_driver
@attr.s(eq=False)
class YAMONDriver(ConsoleBootDriver):
    """Load S-record images over TFTP and boot them with YAMON."""
    prompt = attr.ib(default=r'(?m)(?:^|(?<=\r))YAMON>[ \t]*',
                     validator=attr.validators.instance_of(str))
    autoboot = attr.ib(default=r'Press Ctrl-C to bypass this\.',
                       validator=attr.validators.instance_of(str))
    boot_command = attr.ib(default='go .', validator=attr.validators.instance_of(str))
    reset_command = attr.ib(default='reset', validator=attr.validators.instance_of(str))

    @Driver.check_active
    @step(args=['url'])
    def load(self, url, timeout=120):
        """Load a TFTP S-record image and require YAMON's success summary."""
        return self._execute(f'load {url}', timeout=timeout,
                             expect=r'(?m)^Start\s*=\s*0x[0-9a-fA-F]+,[^\r\n]*format\s*=\s*SREC')
