from unittest.mock import Mock

import pytest

from labgrid import Target
from labgrid.driver import ExecutionError, YAMONDriver
from labgrid.driver.fake import FakeConsoleDriver


@pytest.mark.parametrize('output,success', [
    (b'\r\nStart = 0x80000000, length = 0x1234, format = SREC\r\n', True),
    (b'\r\nError: transfer failed\r\n', False),
    (b'\r\nStart = 0x80000000, format = ELF\r\n', False),
])
def test_load(output, success):
    target = Target('test')
    console = FakeConsoleDriver(target, 'console')
    target.activate(console)
    console.expect = Mock(return_value=(0, b'', None, b'YAMON> '))
    driver = YAMONDriver(target, 'firmware')
    target.activate(driver)
    console.expect.side_effect = [(0, b'', None, b'load tftp://server/kernel'),
                                  (0, output, None, b'YAMON> ')]
    if success:
        driver.load('tftp://server/kernel')
        driver.boot()
        assert console.txq[-1] == b'go .\n'
    else:
        with pytest.raises(ExecutionError):
            driver.load('tftp://server/kernel')
    target.cleanup()
