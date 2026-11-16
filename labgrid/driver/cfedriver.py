"""Broadcom Common Firmware Environment console support."""
import attr

from ..factory import target_factory
from .consolebootdriver import ConsoleBootDriver


@target_factory.reg_driver
@attr.s(eq=False)
class CFEDriver(ConsoleBootDriver):
    """Control CFE, including ARM raw-image and SiByte ELF boot commands.

    Configure boot_command for the image format and board's load address.
    init_commands may configure networking before booting. Commands are never
    passed through a shell or rewritten with U-Boot-specific echo markers.
    """
    prompt = attr.ib(default=r'(?m)(?:^|(?<=\r))CFE>[ \t]*',
                     validator=attr.validators.instance_of(str))
    reset_command = attr.ib(default='reset', validator=attr.validators.instance_of(str))
