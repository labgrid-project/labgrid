import logging

import attr

from ..factory import target_factory
from ..protocol import CommandProtocol, ConsoleProtocol, FileTransferProtocol, PowerProtocol
from .common import Driver
from .commandmixin import CommandMixin
from .consoleexpectmixin import ConsoleExpectMixin


@target_factory.reg_driver
@attr.s
class FakeConsoleDriver(ConsoleExpectMixin, Driver, ConsoleProtocol):
    txdelay = attr.ib(default=0.0, validator=attr.validators.instance_of(float))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.logger = logging.getLogger("{}({})".format(self, self.target))

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
    @Driver.check_active
    def run(self, *args):
        pass

    @Driver.check_active
    def run_check(self, *args):
        pass

    @Driver.check_active
    def get_status(self):
        pass


@target_factory.reg_driver
@attr.s
class FakeFileTransferDriver(Driver, FileTransferProtocol):
    @Driver.check_active
    def get(self, *args):
        pass

    @Driver.check_active
    def put(self, *args):
        pass

@target_factory.reg_driver
@attr.s
class FakePowerDriver(Driver, PowerProtocol):
    @Driver.check_active
    def on(self, *args):
        pass

    @Driver.check_active
    def off(self, *args):
        pass

    @Driver.check_active
    def cycle(self, *args):
        pass
