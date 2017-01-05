import attr

from ..factory import target_factory
from ..protocol import CommandProtocol, ConsoleProtocol
from .common import Driver


@target_factory.reg_driver
@attr.s
class FakeConsoleDriver(Driver, ConsoleProtocol):
    def read(self, *args):
        pass

    def write(self, *args):
        pass

    def open(self):
        pass

    def close(self):
        pass


@target_factory.reg_driver
@attr.s
class FakeCommandDriver(Driver, CommandProtocol):
    def run(self, *args):
        pass

    def run_check(self, *args):
        pass

    def get_status(self):
        pass
