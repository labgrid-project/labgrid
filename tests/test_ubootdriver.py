from types import SimpleNamespace

import pytest
from pexpect import TIMEOUT

from labgrid import Target
from labgrid.driver import UBootDriver, SmallUBootDriver
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

    def test_uboot_await_prompt_timeout_autoboot_loop(self, target_with_fakeconsole, mocker):
        """A board stuck in a reset loop keeps printing the autoboot string.
        _await_prompt must give up after login_timeout, allowing exactly one
        more autoboot match after the deadline."""
        t = target_with_fakeconsole
        d = UBootDriver(t, "uboot", prompt="=> ", login_timeout=1)
        clock = [0.0]
        mocker.patch("labgrid.util.timeout.time", SimpleNamespace(monotonic=lambda: clock[0]))

        def fake_expect(*args, **kwargs):
            if d.console.expect.call_count > 10:
                pytest.fail("_await_prompt did not give up after login_timeout")
            clock[0] += 0.6
            return (1, b"Hit any key to stop autoboot", None, None)

        d.console.expect = mocker.MagicMock(side_effect=fake_expect)
        with pytest.raises(TIMEOUT):
            t.activate(d)
        assert d.console.expect.call_count == 3

    def test_uboot_await_prompt_match_after_deadline(self, target_with_fakeconsole, mocker):
        """An autoboot match that arrives after login_timeout must not fail
        when the prompt follows the interrupt that was just sent."""
        t = target_with_fakeconsole
        d = UBootDriver(t, "uboot", prompt="=> ", login_timeout=1)
        clock = [0.0]
        mocker.patch("labgrid.util.timeout.time", SimpleNamespace(monotonic=lambda: clock[0]))
        responses = [
            (1, b"Hit any key to stop autoboot", None, None),
            (0, b"", None, None),
        ]

        def fake_expect(*args, **kwargs):
            clock[0] += 1.2
            return responses.pop(0)

        d.console.expect = mocker.MagicMock(side_effect=fake_expect)
        d._check_prompt = mocker.MagicMock()
        t.activate(d)
        assert d.console.expect.call_count == 2
        assert d._status == 1

    def test_uboot_await_prompt_password_after_deadline(self, target_with_fakeconsole, mocker):
        """After a late autoboot match the password prompt may follow, it
        must still be answered."""
        t = target_with_fakeconsole
        d = UBootDriver(t, "uboot", prompt="=> ", password="secret", login_timeout=1)
        clock = [0.0]
        mocker.patch("labgrid.util.timeout.time", SimpleNamespace(monotonic=lambda: clock[0]))
        responses = [
            (1, b"Hit any key to stop autoboot", None, None),
            (2, b"enter Password:", None, None),
            (0, b"", None, None),
        ]

        def fake_expect(*args, **kwargs):
            clock[0] += 1.2
            return responses.pop(0)

        d.console.expect = mocker.MagicMock(side_effect=fake_expect)
        d.console.sendline = mocker.MagicMock()
        d._check_prompt = mocker.MagicMock()
        t.activate(d)
        assert d.console.expect.call_count == 3
        d.console.sendline.assert_called_once_with("secret")

    def test_uboot_await_prompt_password_loop(self, target_with_fakeconsole, mocker):
        """A board that keeps printing the password prompt after the password
        was sent must not make _await_prompt spin forever."""
        t = target_with_fakeconsole
        d = UBootDriver(t, "uboot", prompt="=> ", password="secret", login_timeout=1)
        clock = [0.0]
        mocker.patch("labgrid.util.timeout.time", SimpleNamespace(monotonic=lambda: clock[0]))

        def fake_expect(*args, **kwargs):
            if d.console.expect.call_count > 10:
                pytest.fail("_await_prompt did not give up after login_timeout")
            clock[0] += 0.6
            return (2, b"enter Password:", None, None)

        d.console.expect = mocker.MagicMock(side_effect=fake_expect)
        with pytest.raises(TIMEOUT):
            t.activate(d)
        assert d.console.expect.call_count == 3

    def test_uboot_run_not_at_prompt(self, target_with_fakeconsole):
        t = target_with_fakeconsole
        d = UBootDriver(t, "uboot")
        d = t.get_driver(UBootDriver)
        # e.g. after reset() failed to find the prompt again
        d._status = 0
        with pytest.raises(ExecutionError):
            d.run_check("test")
        with pytest.raises(ExecutionError):
            d.run("test")

    def test_smalluboot_run_not_at_prompt(self, target_with_fakeconsole):
        t = target_with_fakeconsole
        d = SmallUBootDriver(t, "uboot")
        d.console.rxq.append(b"U-Boot 2019\n")
        t.activate(d)
        d._status = 0
        with pytest.raises(ExecutionError):
            d.run_check("test")
        with pytest.raises(ExecutionError):
            d.run("test")

    def test_uboot_run_decodeerrors(self, target_with_fakeconsole, mocker):
        t = target_with_fakeconsole
        d = UBootDriver(t, "uboot", prompt="=> ")
        d._await_prompt = mocker.MagicMock()
        t.activate(d)
        d._status = 1
        mocker.patch("labgrid.driver.ubootdriver.gen_marker", return_value="MARKERABCD")
        # command echo, marker, invalid UTF-8 output, exit code, marker, prompt
        d.console.rxq.append(b"echo cmd\r\nMARKERABCD\r\n\xff\r\n0\r\nMARKERABCD\r\n=> ")
        assert d.run_check("test", decodeerrors="replace") == ["\ufffd"]

        d.console.rxq.append(b"echo cmd\r\nMARKERABCD\r\n\xff\r\n0\r\nMARKERABCD\r\n=> ")
        assert d.run_check("test", codec="latin-1") == ["\xff"]

        d.console.rxq.append(b"echo cmd\r\nMARKERABCD\r\n\xff\r\n0\r\nMARKERABCD\r\n=> ")
        with pytest.raises(UnicodeDecodeError):
            d.run_check("test")

    def test_smalluboot_run_decodeerrors(self, target_with_fakeconsole, mocker):
        t = target_with_fakeconsole
        d = SmallUBootDriver(t, "uboot", prompt="=> ")
        d._await_prompt = mocker.MagicMock()
        t.activate(d)
        d._status = 1
        mocker.patch("labgrid.driver.smallubootdriver.gen_marker", return_value="MARKERABCD")
        unknown = b"Unknown command 'echoMARKERABCD' - try 'help'"
        d.console.rxq.append(b"echo cmd\n" + unknown + b"\n\xff\n" + unknown + b"\n=> ")
        assert d.run_check("test", decodeerrors="replace") == ["\ufffd"]

        d.console.rxq.append(b"echo cmd\n" + unknown + b"\n\xff\n" + unknown + b"\n=> ")
        assert d.run_check("test", codec="latin-1") == ["\xff"]
