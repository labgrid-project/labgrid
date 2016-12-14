import attr
from ..protocol import CommandProtocol, ConsoleProtocol, LinuxBootProtocol
from ..factory import target_factory
from .exception import NoDriverError


@target_factory.reg_driver
@attr.s
class BareboxDriver(CommandProtocol, LinuxBootProtocol):
    """BareboxDriver - Driver to control barebox via the console"""
    target = attr.ib()
    prompt = attr.ib(default="", validator=attr.validators.instance_of(str))

    def __attrs_post_init__(self):
        # FIXME: Hard coded for only one driver, should find the correct one in order
        self.console = self.target.get_driver(ConsoleProtocol) #pylint: disable=no-member,attribute-defined-outside-init
        if not self.console:
            raise NoDriverError("Target has no {} driver".format(ConsoleProtocol))
        self.target.drivers.append(self) #pylint: disable=no-member

    def run(self, cmd):
        pass

    def run_check(self, cmd):
        pass

    def get_status(self):
        pass

    def await_boot(self):
        pass

    def boot(self, name):
        pass
