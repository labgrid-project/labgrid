from unittest.mock import Mock

from labgrid import Target
from labgrid.driver import CoLoDriver, ExecutionError
from labgrid.driver.fake import FakeConsoleDriver
import pytest


def test_load_and_boot():
    target = Target('test')
    console = FakeConsoleDriver(target, 'console')
    target.activate(console)
    console.expect = Mock(return_value=(1, b'', None, b'> '))
    driver = CoLoDriver(target, 'firmware', boot_command='exec "console=ttyS0,115200"')
    target.activate(driver)
    console.expect.return_value = (0, b'loaded', None, b'> ')
    driver.load('192.0.2.1', 'cobalt/vmlinux64')
    driver.boot()
    assert console.txq == [b'\x03', b'net\n', b'tftp 192.0.2.1 cobalt/vmlinux64\n',
                            b'exec "console=ttyS0,115200"\n']
    with pytest.raises(ExecutionError, match='power cycling'):
        driver.reset()
    target.cleanup()
