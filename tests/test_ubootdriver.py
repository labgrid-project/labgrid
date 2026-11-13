import pytest

from labgrid import Target
from labgrid.driver import UBootDriver
from labgrid.driver.fake import FakeConsoleDriver
from labgrid.protocol import CommandProtocol, LinuxBootProtocol
from labgrid.driver import ExecutionError


class TestUBootDriver:
    def test_create(self):
        t = Target('dummy')
        cp = FakeConsoleDriver(t, "console")
        d = UBootDriver(t, "uboot")
        assert (isinstance(d, UBootDriver))
        assert (isinstance(d, CommandProtocol))
        assert (isinstance(d, LinuxBootProtocol))

    def test_uboot_run(self, target_with_fakeconsole, mocker):
        t = target_with_fakeconsole
        d = UBootDriver(t, "uboot")
        d.console.rxq.append(b"U-Boot 2019\n")
        d = t.get_driver(UBootDriver)
        d._run = mocker.MagicMock(return_value=(['success'], [], 0))
        res = d.run_check("test")
        assert res == ['success']
        d._run.assert_called_once_with("test", timeout=30, codec='utf-8', decodeerrors='strict')
        d._run.reset_mock()
        res = d.run("test")
        assert res == (['success'], [], 0)
        d._run.assert_called_once_with("test", timeout=30)

    def test_uboot_run_error(self, target_with_fakeconsole, mocker):
        t = target_with_fakeconsole
        d = UBootDriver(t, "uboot")
        d.console.rxq.append(b"U-Boot 2019\n")
        d = t.get_driver(UBootDriver)
        d._run = mocker.MagicMock(return_value=(['error'], [], 1))
        with pytest.raises(ExecutionError):
            res = d.run_check("test")
        d._run.assert_called_once_with("test", timeout=30, codec='utf-8', decodeerrors='strict')
        d._run.reset_mock()
        res = d.run("test")
        assert res == (['error'], [], 1)
        d._run.assert_called_once_with("test", timeout=30)

    def test_uboot_boot(self, target_with_fakeconsole):
        t = target_with_fakeconsole
        d = UBootDriver(t, "uboot", boot_command='run bootcmd', boot_commands = {"foo": "bar"})
        d = t.get_driver(UBootDriver)
        d.boot()
        assert d.console.txq.pop() == b"run bootcmd\n"
        d.boot('foo')
        assert d.console.txq.pop() == b"bar\n"
        with pytest.raises(Exception):
            d.boot('nop')


def test_early_interrupt(target_with_fakeconsole, monkeypatch):
    from unittest.mock import Mock
    from pexpect import TIMEOUT

    target = target_with_fakeconsole
    driver = UBootDriver(target, "uboot", prompt='Viper>> ', interrupt='\x03',
                         interrupt_interval=0.1, settle_time=0.5)
    target.activate(driver.console)
    driver.console.expect = Mock(side_effect=[(3, b'', None, b''),
                                              (0, b'', None, b'Viper>> '),
                                              (0, b'', None, b'Viper>> ')])
    driver.console.settle = Mock(return_value=True)
    monkeypatch.setattr(driver, '_check_prompt', lambda: None)
    target.activate(driver)
    assert driver.console.txq == [b'\x03', b'\x03', b'\n']
    driver.console.settle.assert_called_once()
    assert driver.console.expect.call_args_list[0].args[0][-1] is TIMEOUT


@pytest.mark.parametrize('option', ['interrupt_interval', 'settle_time'])
def test_negative_timing(target_with_fakeconsole, option):
    with pytest.raises(ValueError, match='interrupt_interval and settle_time must be nonnegative'):
        UBootDriver(target_with_fakeconsole, "uboot", **{option: -0.1})


def test_early_interrupt_login_timeout(target_with_fakeconsole, mocker):
    from pexpect import TIMEOUT

    target = target_with_fakeconsole
    driver = UBootDriver(target, "uboot", login_timeout=0, interrupt_interval=0.1)
    target.activate(driver.console)
    expect = mocker.patch.object(driver.console, 'expect')

    with pytest.raises(TIMEOUT, match='Timeout of 0 seconds waiting for U-Boot'):
        target.activate(driver)

    expect.assert_not_called()
    assert driver.console.txq == []


def test_early_interrupt_settle_timeout(target_with_fakeconsole, mocker):
    from pexpect import TIMEOUT

    target = target_with_fakeconsole
    driver = UBootDriver(target, "uboot", prompt='Viper>> ', interrupt='\x03',
                         interrupt_interval=0.1, settle_time=0.5)
    target.activate(driver.console)
    expect = mocker.patch.object(driver.console, 'expect', return_value=(0, b'', None, b'Viper>> '))
    settle = mocker.patch.object(driver.console, 'settle', return_value=False)
    check_prompt = mocker.patch.object(driver, '_check_prompt')

    with pytest.raises(TIMEOUT, match='U-Boot console did not settle'):
        target.activate(driver)

    settle.assert_called_once_with(0.5, timeout=mocker.ANY)
    assert 0 < settle.call_args.kwargs['timeout'] <= driver.login_timeout
    assert expect.call_count == 1
    check_prompt.assert_not_called()
    assert driver.console.txq == [b'\x03']
