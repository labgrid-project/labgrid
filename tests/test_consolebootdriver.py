from unittest.mock import Mock

import pytest
from pexpect import TIMEOUT

from labgrid import Target
from labgrid.driver import CFEDriver, ExecutionError
from labgrid.driver.fake import FakeConsoleDriver
from labgrid.protocol import CommandProtocol, LinuxBootProtocol


@pytest.fixture
def firmware():
    target = Target('test')
    console = FakeConsoleDriver(target, 'console')
    target.activate(console)
    console.expect = Mock(return_value=(0, b'', None, b'CFE> '))
    driver = CFEDriver(target, 'firmware', boot_command='boot -elf server:kernel')
    target.activate(driver)
    yield driver, console
    target.cleanup()


def test_activation(firmware):
    driver, console = firmware
    assert isinstance(driver, LinuxBootProtocol)
    assert not isinstance(driver, CommandProtocol)
    assert console.txq == [b'\x03']
    driver.boot()
    assert console.txq[-1] == b'boot -elf server:kernel\n'
    driver.await_boot()
    assert console.expect.call_args.args == (r'Linux version\s',)


def test_command_success(firmware):
    driver, console = firmware
    console.expect.side_effect = [(0, b'', None, b'load kernel'),
                                  (0, b'\r\nStart = 0x1234, format = SREC\r\n', None, b'CFE> ')]
    assert 'SREC' in driver.run_command('load kernel', expect='format = SREC')
    assert console.expect.call_args_list[-2].args[0] == r'load\ kernel'


def test_command_failure(firmware):
    driver, console = firmware
    with pytest.raises(ExecutionError, match='expected output'):
        driver.run_command('load kernel', expect='format = SREC')


def test_named_boot(firmware):
    driver, console = firmware
    driver.boot_commands['recovery'] = 'boot -raw server:recovery'
    driver.boot('recovery')
    assert console.txq[-1] == b'boot -raw server:recovery\n'
    with pytest.raises(KeyError):
        driver.boot('missing')


def test_repeated_interrupt():
    target = Target('test')
    console = FakeConsoleDriver(target, 'console')
    target.activate(console)
    console.expect = Mock(side_effect=[(1, b'', None, b''), (0, b'', None, b'CFE> ')])
    driver = CFEDriver(target, 'firmware')
    target.activate(driver)
    assert console.txq == [b'\x03', b'\x03']
    target.cleanup()


def test_banner_interrupt():
    target = Target('test')
    console = FakeConsoleDriver(target, 'console')
    target.activate(console)
    console.expect = Mock(side_effect=[(1, b'', None, b'booting'), (0, b'', None, b'CFE> ')])
    driver = CFEDriver(target, 'firmware', autoboot='booting')
    target.activate(driver)
    assert console.txq == [b'\x03']
    target.cleanup()


def test_timeout(firmware):
    driver, console = firmware
    console.expect.side_effect = TIMEOUT('missing prompt')
    with pytest.raises(TIMEOUT):
        driver.run_command('bad')


def test_reset(firmware):
    driver, console = firmware
    driver.reset()
    assert b'reset\n' in console.txq
    assert driver._ready


@pytest.mark.parametrize('driver_name,banner,prompt,command,summary,boot', [
    ('CFEDriver', '', 'CFE> ', 'ifconfig eth0 -auto', 'Link up', 'boot -elf server:kernel'),
    ('YAMONDriver', 'Press Ctrl-C to bypass this.\r\n', 'YAMON> ', 'load tftp://server/kernel',
     'Start = 0x80000000, length = 0x1234, format = SREC', 'go .'),
    ('CoLoDriver', 'boot: running boot menu\r\n', '> ', 'tftp server kernel', 'loaded kernel', 'exec'),
])
def test_firmware_transcript(driver_name, banner, prompt, command, summary, boot):
    import labgrid.driver

    target = Target('test')
    console = FakeConsoleDriver(target, 'console')
    console.rxq.append((banner + prompt + command + '\r\n' + summary + '\r\n' + prompt
                        + 'Linux version 6.19.0\r\n').encode())
    driver = getattr(labgrid.driver, driver_name)(
        target, 'firmware', init_commands=[{'command': command, 'expect': summary}], boot_command=boot)
    target.activate(driver)
    driver.boot()
    driver.await_boot()
    assert console.txq[-2:] == [(command + '\n').encode(), (boot + '\n').encode()]
    target.cleanup()
