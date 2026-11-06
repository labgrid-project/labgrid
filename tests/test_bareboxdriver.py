from types import SimpleNamespace

import pytest
from pexpect import TIMEOUT

from labgrid import Target
from labgrid.driver import BareboxDriver
from labgrid.driver.fake import FakeConsoleDriver
from labgrid.protocol import CommandProtocol, LinuxBootProtocol
from labgrid.driver import ExecutionError


class TestBareboxDriver:
    def test_create(self):
        t = Target('dummy')
        cp = FakeConsoleDriver(t, "console")
        d = BareboxDriver(t, "barebox")
        assert (isinstance(d, BareboxDriver))
        assert (isinstance(d, CommandProtocol))
        assert (isinstance(d, LinuxBootProtocol))

    def test_barebox_run(self, target_with_fakeconsole, mocker):
        t = target_with_fakeconsole
        d = BareboxDriver(t, "barebox")
        d = t.get_driver(BareboxDriver, activate=False)
        # mock for d._run('echo $global.loglevel')
        d._run = mocker.MagicMock(return_value=(['7'], [], 0))
        t.activate(d)
        d._run = mocker.MagicMock(return_value=(['success'], [], 0))
        res = d.run_check("test")
        assert res == ['success']
        res = d.run("test")
        assert res == (['success'], [], 0)

    def test_barebox_run_error(self, target_with_fakeconsole, mocker):
        t = target_with_fakeconsole
        d = BareboxDriver(t, "barebox")
        d = t.get_driver(BareboxDriver, activate=False)
        # mock for d._run('echo $global.loglevel')
        d._run = mocker.MagicMock(return_value=(['7'], [], 0))
        t.activate(d)
        d._run = mocker.MagicMock(return_value=(['error'], [], 1))
        with pytest.raises(ExecutionError):
            res = d.run_check("test")
        res = d.run("test")
        assert res == (['error'], [], 1)

    def test_barebox_boot(self, target_with_fakeconsole, mocker):
        t = target_with_fakeconsole
        d = BareboxDriver(t, "barebox", boot_command='boot -v foo')
        d = t.get_driver(BareboxDriver, activate=False)
        # mock for d._run('echo $global.loglevel')
        d._run = mocker.MagicMock(return_value=(['7'], [], 0))
        t.activate(d)
        d._run = mocker.MagicMock(return_value=(['success'], [], 0))
        d.boot()
        assert d.console.txq.pop() == b"boot -v foo\n"
        d.boot(name='bar')
        assert d.console.txq.pop() == b"boot -v bar\n"

    def test_barebox_await_prompt_timeout_autoboot_loop(self, target_with_fakeconsole, mocker):
        """A board stuck in a reset loop keeps printing the autoboot string.
        _await_prompt must give up after login_timeout, allowing exactly one
        more autoboot match after the deadline."""
        t = target_with_fakeconsole
        d = BareboxDriver(t, "barebox", prompt="barebox@board:/ ", login_timeout=1)
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

    def test_barebox_await_prompt_match_after_deadline(self, target_with_fakeconsole, mocker):
        """An autoboot match that arrives after login_timeout must not fail
        when the prompt follows the interrupt that was just sent."""
        t = target_with_fakeconsole
        d = BareboxDriver(t, "barebox", prompt="barebox@board:/ ", login_timeout=1)
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
        d._run = mocker.MagicMock(return_value=(["7"], [], 0))
        t.activate(d)
        assert d.console.expect.call_count == 2

    def test_barebox_await_prompt_password_after_deadline(self, target_with_fakeconsole, mocker):
        """After a late autoboot match the password prompt may follow, it
        must still be answered."""
        t = target_with_fakeconsole
        d = BareboxDriver(t, "barebox", prompt="barebox@board:/ ", password="secret", login_timeout=1)
        clock = [0.0]
        mocker.patch("labgrid.util.timeout.time", SimpleNamespace(monotonic=lambda: clock[0]))
        responses = [
            (1, b"Hit any key to stop autoboot", None, None),
            (2, b"Password: ", None, None),
            (0, b"", None, None),
        ]

        def fake_expect(*args, **kwargs):
            clock[0] += 1.2
            return responses.pop(0)

        d.console.expect = mocker.MagicMock(side_effect=fake_expect)
        d.console.sendline = mocker.MagicMock()
        d._check_prompt = mocker.MagicMock()
        d._run = mocker.MagicMock(return_value=(["7"], [], 0))
        t.activate(d)
        assert d.console.expect.call_count == 3
        d.console.sendline.assert_called_once_with("secret")

    def test_barebox_run_not_at_prompt(self, target_with_fakeconsole, mocker):
        t = target_with_fakeconsole
        d = BareboxDriver(t, "barebox")
        d = t.get_driver(BareboxDriver, activate=False)
        # mock for d._run('echo $global.loglevel')
        d._run = mocker.MagicMock(return_value=(['7'], [], 0))
        t.activate(d)
        del d._run  # use the real _run again
        # e.g. after reset() failed to find the prompt again
        d._status = 0
        with pytest.raises(ExecutionError):
            d.run_check("test")
        with pytest.raises(ExecutionError):
            d.run("test")

    def test_barebox_run_decodeerrors(self, target_with_fakeconsole, mocker):
        t = target_with_fakeconsole
        d = BareboxDriver(t, "barebox", prompt="barebox@board:/ ")
        d._await_prompt = mocker.MagicMock()
        t.activate(d)
        d._status = 1
        mocker.patch("labgrid.driver.bareboxdriver.gen_marker", return_value="MARKERABCD")
        # marker, invalid UTF-8 output, marker + exit code, prompt
        d.console.rxq.append(b"MARKERABCD\r\n\xff\r\nMARKERABCD 0\r\nbarebox@board:/ ")
        assert d.run_check("test", decodeerrors="replace") == ["\ufffd"]

        d.console.rxq.append(b"MARKERABCD\r\n\xff\r\nMARKERABCD 0\r\nbarebox@board:/ ")
        assert d.run_check("test", codec="latin-1") == ["\xff"]

        d.console.rxq.append(b"MARKERABCD\r\n\xff\r\nMARKERABCD 0\r\nbarebox@board:/ ")
        with pytest.raises(UnicodeDecodeError):
            d.run_check("test")

    def test_barebox_loglevel_unexpected_output(self, target_with_fakeconsole, mocker):
        """Extra output lines while reading the log level must not break
        activation, the default log level is kept in that case."""
        t = target_with_fakeconsole
        d = BareboxDriver(t, "barebox")
        d = t.get_driver(BareboxDriver, activate=False)
        # mock for d._run('echo $global.loglevel')
        d._run = mocker.MagicMock(return_value=(['some async message', '5'], [], 0))
        t.activate(d)
        assert d.saved_log_level == 7

    def test_barebox_loglevel_saved(self, target_with_fakeconsole, mocker):
        t = target_with_fakeconsole
        d = BareboxDriver(t, "barebox")
        d = t.get_driver(BareboxDriver, activate=False)
        d._run = mocker.MagicMock(return_value=(['5'], [], 0))
        t.activate(d)
        assert d.saved_log_level == '5'
