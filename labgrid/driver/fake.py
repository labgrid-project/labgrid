import attr

from ..factory import target_factory
from ..protocol import CommandProtocol, ConsoleProtocol, FileTransferProtocol, PowerProtocol
from .common import Driver
from .commandmixin import CommandMixin
from .consoleexpectmixin import ConsoleExpectMixin


@target_factory.reg_driver
@attr.s
class FakeConsoleDriver(ConsoleExpectMixin, Driver, ConsoleProtocol):
    def _read(self, *args):
        pass

    def _write(self, *args):
        pass

    def open(self):
        pass

    def close(self):
        pass


@target_factory.reg_driver
@attr.s
class FakeCommandDriver(CommandMixin, Driver, CommandProtocol):
    def run(self, *args):
        pass

    def run_check(self, *args):
        pass

    def get_status(self):
        pass


@target_factory.reg_driver
@attr.s
class FakeFileTransferDriver(Driver, FileTransferProtocol):
    def get(self, *args):
        pass

    def put(self, *args):
        pass

@target_factory.reg_driver
@attr.s
class FakePowerDriver(Driver, PowerProtocol):
    def on(self, *args):
        pass

    def off(self, *args):
        pass

    def cycle(self, *args):
        pass
