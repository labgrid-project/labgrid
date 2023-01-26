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
