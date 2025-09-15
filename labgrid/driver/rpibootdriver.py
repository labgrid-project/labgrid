import attr

from ..factory import target_factory
from ..step import step
from .common import Driver
from ..util.helper import processwrapper

@target_factory.reg_driver
@attr.s(eq=False)
class RpibootDriver(Driver):
    bindings = {
        "rpi": {"RpibootDevice", "NetworkRpibootDevice"},
        }

    image = attr.ib(default=None)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.target.env:
            self.tool = self.target.env.config.get_tool('rpiboot')
        else:
            self.tool = 'rpiboot'

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass

    @Driver.check_active
    @step(args=['filename'])
    def enable(self, filename=None,):
        # Switch raspberry pi into MassStorageDevice mode using the rpiboot tool
        args = []
        processwrapper.check_output(
            self.rpi.command_prefix + [self.tool] + args,
            print_on_silent_log=True
        )
