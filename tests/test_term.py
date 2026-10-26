"""Tests for labgrid.util.term — terminal handling"""

import asyncio
import io
import logging
import os
import sys
import threading
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from labgrid.util.term import external, run, internal, EXIT_CHAR, EXIT_WINDOW
from pexpect import TIMEOUT
from prompt_toolkit.input import create_input
from serial.serialutil import SerialException


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_resource():
    resource = MagicMock()
    resource.speed = 115200
    return resource


@pytest.fixture
def mock_console():
    cons = MagicMock()
    cons.txdelay = 0
    cons.read = MagicMock(side_effect=TIMEOUT("timeout"))
    cons._write = MagicMock()
    return cons


class FakeConsole:
    """Minimal console for pipe-based tests.

    Args:
        txdelay: per-chunk transmit delay in seconds
        txchunk: number of bytes to send between each txdelay
        on_write: optional callback invoked with each chunk written
    """
    def __init__(self, txdelay=0, txchunk=1, on_write=None):
        self.txdelay = txdelay
        self.txchunk = txchunk
        self.written = []
        self._on_write = on_write

    def read(self, size=1024, timeout=0.001):
        raise TIMEOUT("timeout")

    def _write(self, data):
        self.written.append(data)
        if self._on_write:
            self._on_write(data)


@pytest.fixture
def stdin_pipe():
    """Create a pipe and yield (input, write_fd).

    The read side is wrapped in a prompt_toolkit Input, which is what
    run() reads keystrokes from.  Both ends are closed on cleanup.
    """
    read_fd, write_fd = os.pipe()
    # Text mode, since create_input() wants an encoding
    read_file = os.fdopen(read_fd, 'r')
    inp = create_input(read_file)
    yield inp, write_fd
    inp.close()
    read_file.close()
    try:
        os.close(write_fd)
    except OSError:
        pass  # already closed by the test


# --- external() tests ---

class TestExternal:
    def test_microcom_basic(self, event_loop, mock_resource):
        """Test that external() launches microcom when available"""
        proc = AsyncMock()
        proc.returncode = 0
        proc.wait = AsyncMock(return_value=0)
        proc.terminate = MagicMock()

        with patch("labgrid.util.term.shutil.which", return_value="/usr/bin/microcom"), \
             patch("labgrid.util.term.asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc) as mock_exec:
            result = event_loop.run_until_complete(
                external(lambda: None, "host1", 1234, mock_resource, None, False))

            args = mock_exec.call_args[0]
            assert args[0] == "/usr/bin/microcom"
            assert "-s" in args
            assert "115200" in args
            assert "-t" in args
            assert "host1:1234" in args
            assert result == 0

    def test_microcom_listen_only(self, event_loop, mock_resource):
        """Test that --listenonly is passed to microcom"""
        proc = AsyncMock()
        proc.returncode = 0
        proc.wait = AsyncMock(return_value=0)

        with patch("labgrid.util.term.shutil.which", return_value="/usr/bin/microcom"), \
             patch("labgrid.util.term.asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc) as mock_exec:
            event_loop.run_until_complete(
                external(lambda: None, "host1", 1234, mock_resource, None, True))

            args = mock_exec.call_args[0]
            assert "--listenonly" in args

    def test_telnet_fallback(self, event_loop, mock_resource):
        """Test fallback to telnet when microcom is not available"""
        proc = AsyncMock()
        proc.returncode = 0
        proc.wait = AsyncMock(return_value=0)

        with patch("labgrid.util.term.shutil.which", return_value=None), \
             patch("labgrid.util.term.asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc) as mock_exec:
            event_loop.run_until_complete(
                external(lambda: None, "host1", 1234, mock_resource, None, False))

            args = mock_exec.call_args[0]
            assert args[0] == "telnet"
            assert "host1" in args
            assert "1234" in args

    def test_telnet_listen_only_warns(self, event_loop, mock_resource, caplog):
        """Test that telnet with listen_only logs a warning"""
        proc = AsyncMock()
        proc.returncode = 0
        proc.wait = AsyncMock(return_value=0)

        with patch("labgrid.util.term.shutil.which", return_value=None), \
             patch("labgrid.util.term.asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc), \
             caplog.at_level(logging.WARNING):
            event_loop.run_until_complete(
                external(lambda: None, "host1", 1234, mock_resource, None, True))

            assert "--listenonly option not supported by telnet" in caplog.text

    def test_telnet_logfile_warns(self, event_loop, mock_resource, caplog):
        """Test that telnet with logfile logs a warning"""
        proc = AsyncMock()
        proc.returncode = 0
        proc.wait = AsyncMock(return_value=0)

        with patch("labgrid.util.term.shutil.which", return_value=None), \
             patch("labgrid.util.term.asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc), \
             caplog.at_level(logging.WARNING):
            event_loop.run_until_complete(
                external(lambda: None, "host1", 1234, mock_resource, "/tmp/log", False))

            assert "--logfile option not supported by telnet" in caplog.text

    def test_check_allowed_terminates(self, event_loop, mock_resource):
        """Test that check_allowed returning truthy terminates the process"""
        call_count = [0]

        def check():
            call_count[0] += 1
            return "not allowed" if call_count[0] >= 2 else None

        proc = AsyncMock()
        proc.returncode = None

        def do_terminate():
            proc.returncode = -15
        proc.terminate = MagicMock(side_effect=do_terminate)

        wait_count = [0]
        async def fake_wait():
            wait_count[0] += 1
            if wait_count[0] == 1:
                # First call: simulate poll timeout
                await asyncio.sleep(10)
            # Subsequent calls: return immediately (process terminated)
        proc.wait = fake_wait

        with patch("labgrid.util.term.shutil.which", return_value="/usr/bin/microcom"), \
             patch("labgrid.util.term.asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc):
            event_loop.run_until_complete(
                external(check, "host1", 1234, mock_resource, None, False))

            proc.terminate.assert_called_once()

    def test_check_allowed_kills_after_terminate_timeout(self, event_loop, mock_resource):
        """Test that kill is used when terminate does not stop the process.

        This test takes ~3s because three asyncio.wait_for(timeout=1.0)
        calls must time out (two poll loops + one after terminate).
        """
        call_count = [0]

        def check():
            call_count[0] += 1
            return "not allowed" if call_count[0] >= 2 else None

        proc = MagicMock()
        proc.returncode = None
        proc.terminate = MagicMock()  # terminate does NOT set returncode

        def do_kill():
            proc.returncode = -9
        proc.kill = MagicMock(side_effect=do_kill)

        wait_count = [0]
        async def fake_wait():
            wait_count[0] += 1
            if wait_count[0] <= 3:
                # First three calls hang: two poll loops + after terminate
                await asyncio.sleep(10)
            # Fourth call (after kill): return immediately
        proc.wait = fake_wait

        with patch("labgrid.util.term.shutil.which", return_value="/usr/bin/microcom"), \
             patch("labgrid.util.term.asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc):
            event_loop.run_until_complete(
                external(check, "host1", 1234, mock_resource, None, False))

            proc.terminate.assert_called_once()
            proc.kill.assert_called_once()

    def test_microcom_logfile_not_duplicated(self, event_loop, mock_resource):
        """Test that --logfile is not appended twice when using microcom"""
        proc = AsyncMock()
        proc.returncode = 0
        proc.wait = AsyncMock(return_value=0)

        with patch("labgrid.util.term.shutil.which", return_value="/usr/bin/microcom"), \
             patch("labgrid.util.term.asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc) as mock_exec:
            event_loop.run_until_complete(
                external(lambda: None, "host1", 1234, mock_resource, "/tmp/log", False))

            args = mock_exec.call_args[0]
            logfile_args = [a for a in args if "logfile" in str(a)]
            assert len(logfile_args) == 1, f"--logfile appended {len(logfile_args)} times: {args}"

    def test_nonzero_return(self, event_loop, mock_resource, capsys):
        """Test that non-zero return code prints connection lost"""
        proc = AsyncMock()
        proc.returncode = 1
        proc.wait = AsyncMock(return_value=1)

        with patch("labgrid.util.term.shutil.which", return_value="/usr/bin/microcom"), \
             patch("labgrid.util.term.asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc):
            result = event_loop.run_until_complete(
                external(lambda: None, "host1", 1234, mock_resource, None, False))
            assert result == 1
            assert "connection lost" in capsys.readouterr().err


# --- run() tests ---

class TestRun:
    def test_exit_on_double_ctrl_bracket(self, event_loop, mock_console, stdin_pipe):
        """Test that double Ctrl+] exits the loop"""
        inp, write_fd = stdin_pipe
        os.write(write_fd, bytes([EXIT_CHAR, EXIT_CHAR]))

        # Safety net, in case the exit char is not noticed
        start = time.monotonic()
        def check():
            return "timeout" if time.monotonic() - start > 5 else None

        with patch("sys.stdout", new_callable=lambda: MagicMock(spec=sys.stdout)):
            result = event_loop.run_until_complete(
                run(check, mock_console, None, False, inp))

        assert time.monotonic() - start < 5, "did not exit on double Ctrl-]"
        assert result == 0

        # The exit chars are for us, so the board should not see them
        mock_console._write.assert_not_called()

    def test_listen_only_no_stdin_read(self, event_loop, mock_console):
        """Test that listen_only mode does not read from stdin"""
        call_count = [0]
        def check():
            call_count[0] += 1
            return "done" if call_count[0] >= 2 else None

        with patch("os.read") as mock_read, \
             patch("sys.stdout", new_callable=lambda: MagicMock(spec=sys.stdout)):
            event_loop.run_until_complete(
                run(check, mock_console, None, True))
            mock_read.assert_not_called()

    def test_console_output_written_to_stdout(self, event_loop, mock_console):
        """Test that console output is written to stdout"""
        read_count = [0]
        def mock_read(size=1024, timeout=0.001):
            read_count[0] += 1
            if read_count[0] == 1:
                return b"Hello from board\n"
            raise TIMEOUT("timeout")

        mock_console.read = mock_read

        check_count = [0]
        def check():
            check_count[0] += 1
            return "done" if check_count[0] >= 3 else None

        stdout_buffer = io.BytesIO()
        mock_stdout = MagicMock()
        mock_stdout.buffer = stdout_buffer
        mock_stdout.write = MagicMock()
        mock_stdout.flush = MagicMock()

        with patch("sys.stdout", mock_stdout):
            event_loop.run_until_complete(
                run(check, mock_console, None, True))

            stdout_buffer.seek(0)
            assert b"Hello from board\n" in stdout_buffer.getvalue()

    def test_logfile_written(self, event_loop, mock_console):
        """Test that console output is written to the logfile"""
        read_count = [0]
        def mock_read(size=1024, timeout=0.001):
            read_count[0] += 1
            if read_count[0] == 1:
                return b"log data\n"
            raise TIMEOUT("timeout")

        mock_console.read = mock_read

        check_count = [0]
        def check():
            check_count[0] += 1
            return "done" if check_count[0] >= 3 else None

        log_fd = io.BytesIO()

        with patch("sys.stdout", new_callable=lambda: MagicMock(spec=sys.stdout)):
            event_loop.run_until_complete(
                run(check, mock_console, log_fd, True))

        log_fd.seek(0)
        assert b"log data\n" in log_fd.getvalue()

    def test_serial_exception_exits(self, event_loop, mock_console, capsys):
        """Test that SerialException breaks out of the loop with an error"""
        mock_console.read = MagicMock(side_effect=SerialException("disconnected"))

        result = event_loop.run_until_complete(
            run(lambda: None, mock_console, None, True))
        assert result == 1
        assert "connection lost" in capsys.readouterr().err

    def test_stdin_written_to_console(self, event_loop, stdin_pipe):
        """Test that stdin data is written to the console in one go when there
        is no txdelay, using a pipe for stdin rather than mocking os.read"""
        inp, write_fd = stdin_pipe
        os.write(write_fd, b"Hi")
        os.close(write_fd)

        cons = FakeConsole()

        # Exit once both bytes are written
        def check():
            return "done" if len(b"".join(cons.written)) >= 2 else None

        with patch("sys.stdout", new_callable=lambda: MagicMock(spec=sys.stdout)):
            event_loop.run_until_complete(
                run(check, cons, None, False, inp))

        assert cons.written == [b"Hi"]

    def test_raw_bytes_passed_through(self, event_loop, stdin_pipe):
        """Test that what the user types reaches the board untouched

        prompt_toolkit's read_keys() would turn these into key objects, so
        check that the raw bytes are sent instead, since the board needs a
        transparent stream.
        """
        inp, write_fd = stdin_pipe
        keys = b"\x1b[A\x1bOP\x03\xc3\xa9"  # Up arrow, F1, Ctrl-C, é
        os.write(write_fd, keys)
        os.close(write_fd)

        cons = FakeConsole()

        def check():
            return "done" if len(b"".join(cons.written)) >= len(keys) else None

        with patch("sys.stdout", new_callable=lambda: MagicMock(spec=sys.stdout)):
            event_loop.run_until_complete(
                run(check, cons, None, False, inp))

        assert b"".join(cons.written) == keys

    def test_stdin_txdelay(self, event_loop, stdin_pipe):
        """Test that txdelay throttles bytes written to the console"""
        inp, write_fd = stdin_pipe
        os.write(write_fd, b"AB")
        os.close(write_fd)

        timestamps = []
        def record_time(data):
            timestamps.append(time.monotonic())

        cons = FakeConsole(txdelay=0.05, on_write=record_time)

        def check():
            return "done" if len(timestamps) >= 2 else None

        with patch("sys.stdout", new_callable=lambda: MagicMock(spec=sys.stdout)):
            event_loop.run_until_complete(
                run(check, cons, None, False, inp))

        assert len(timestamps) == 2
        gap = timestamps[1] - timestamps[0]
        # Allow 10ms margin below the 50ms txdelay for scheduling jitter
        assert gap >= 0.04

    def run_feeder(self, event_loop, inp, cons, feed, done):
        """Run the loop while a thread types into the terminal

        Args:
            inp: prompt_toolkit Input to pass to run()
            cons: console to pass to run()
            feed: function to call in a thread to type things
            done: function returning True when the loop should stop

        Returns:
            int: Result from run()
        """
        threading.Thread(target=feed, daemon=True).start()

        # Safety net, in case the loop does not stop by itself
        start = time.monotonic()
        def check():
            if time.monotonic() - start > 5:
                return "timeout"
            return "done" if done() else None

        with patch("sys.stdout", new_callable=lambda: MagicMock(spec=sys.stdout)):
            result = event_loop.run_until_complete(
                run(check, cons, None, False, inp))
        assert time.monotonic() - start < 5, "loop did not stop"
        return result

    def test_exit_chars_typed_separately(self, event_loop, stdin_pipe):
        """Test that Ctrl-] pressed twice exits, without sending the first one

        Unlike test_exit_on_double_ctrl_bracket(), the two characters arrive
        separately, as they do when someone presses the keys.
        """
        inp, write_fd = stdin_pipe
        cons = FakeConsole()

        def feed():
            os.write(write_fd, bytes([EXIT_CHAR]))
            time.sleep(EXIT_WINDOW / 4)
            os.write(write_fd, bytes([EXIT_CHAR]))

        result = self.run_feeder(event_loop, inp, cons, feed, lambda: False)
        assert result == 0
        assert not cons.written

    def test_exit_char_then_other(self, event_loop, stdin_pipe):
        """Test that a Ctrl-] followed by another key is sent to the board"""
        inp, write_fd = stdin_pipe
        cons = FakeConsole()

        def feed():
            os.write(write_fd, bytes([EXIT_CHAR]))
            time.sleep(EXIT_WINDOW / 4)
            os.write(write_fd, b"X")

        self.run_feeder(event_loop, inp, cons, feed,
                        lambda: b"X" in b"".join(cons.written))
        assert b"".join(cons.written) == bytes([EXIT_CHAR]) + b"X"

    def test_lone_exit_char_sent(self, event_loop, stdin_pipe):
        """Test that a single Ctrl-] is sent to the board after the window

        Nothing is sent until the window expires, since a second Ctrl-] may
        follow. A Ctrl-] after that starts a new window, so the two of them
        do not cause an exit.
        """
        inp, write_fd = stdin_pipe
        cons = FakeConsole()
        sent_early = []

        def feed():
            os.write(write_fd, bytes([EXIT_CHAR]))
            time.sleep(EXIT_WINDOW / 2)
            sent_early.append(bool(cons.written))
            time.sleep(EXIT_WINDOW)
            os.write(write_fd, bytes([EXIT_CHAR]) + b"X")

        self.run_feeder(event_loop, inp, cons, feed,
                        lambda: b"X" in b"".join(cons.written))
        assert sent_early == [False]
        assert b"".join(cons.written) == bytes([EXIT_CHAR, EXIT_CHAR]) + b"X"

    def test_txdelay_after_idle(self, event_loop, stdin_pipe):
        """Test that txdelay still applies when the console has been idle"""
        inp, write_fd = stdin_pipe
        timestamps = []
        cons = FakeConsole(txdelay=0.05,
                           on_write=lambda data: timestamps.append(time.monotonic()))

        def feed():
            time.sleep(0.2)
            os.write(write_fd, b"AB")

        self.run_feeder(event_loop, inp, cons, feed,
                        lambda: len(timestamps) >= 2)
        # Allow 10ms margin below the 50ms txdelay for scheduling jitter
        assert timestamps[1] - timestamps[0] >= 0.04

    def test_txchunk(self, event_loop, stdin_pipe):
        """Test that txchunk bytes are sent between each txdelay"""
        inp, write_fd = stdin_pipe
        os.write(write_fd, b"ABCDEFG")
        os.close(write_fd)

        cons = FakeConsole(txdelay=0.01, txchunk=3)

        def check():
            return "done" if len(b"".join(cons.written)) >= 7 else None

        with patch("sys.stdout", new_callable=lambda: MagicMock(spec=sys.stdout)):
            event_loop.run_until_complete(
                run(check, cons, None, False, inp))

        assert cons.written == [b"ABC", b"DEF", b"G"]

    def test_ready_message(self, event_loop, mock_console, stdin_pipe):
        """Test that the message tells the user how to exit"""
        inp, _ = stdin_pipe
        for term_inp, expect in ((inp, "Ctrl-] twice"), (None, "Ctrl-C")):
            stdout = MagicMock(spec=sys.stdout)
            with patch("sys.stdout", stdout):
                event_loop.run_until_complete(
                    run(lambda: "done", mock_console, None, term_inp is None,
                        term_inp))
            assert expect in stdout.write.call_args_list[0][0][0]

    def test_check_allowed_exits(self, event_loop, mock_console):
        """Test that check_allowed returning an error exits the loop"""
        with patch("sys.stdout", new_callable=lambda: MagicMock(spec=sys.stdout)):
            result = event_loop.run_until_complete(
                run(lambda: "not allowed", mock_console, None, True))
        assert result == 0


# --- internal() tests ---

class TestInternal:
    def test_listen_only_no_terminal_setup(self, event_loop, mock_console):
        """Test that listen_only mode skips terminal setup"""
        with patch("labgrid.util.term.run", new_callable=AsyncMock,
                   return_value=0) as mock_run, \
             patch("labgrid.util.term.create_input") as mock_create_input:
            result = event_loop.run_until_complete(
                internal(lambda: None, mock_console, None, True))

            mock_create_input.assert_not_called()
            mock_run.assert_awaited_once()
            # The keyboard is not watched, so run() gets no terminal
            assert mock_run.await_args[0][4] is None
            assert result == 0

    def test_with_logfile(self, event_loop, mock_console, tmp_path):
        """Test that a logfile is opened and closed"""
        logfile = str(tmp_path / "test.log")

        with patch("labgrid.util.term.run", new_callable=AsyncMock,
                   return_value=0):
            result = event_loop.run_until_complete(
                internal(lambda: None, mock_console, logfile, True))

            assert result == 0
            assert os.path.exists(logfile)

    def test_run_result_returned(self, event_loop, mock_console):
        """Test that a lost console is reported by internal()"""
        with patch("labgrid.util.term.run", new_callable=AsyncMock,
                   return_value=1):
            result = event_loop.run_until_complete(
                internal(lambda: None, mock_console, None, True))
            assert result == 1

    def test_os_error_returns_1(self, event_loop, mock_console):
        """Test that OSError during run returns exitcode 1"""
        with patch("labgrid.util.term.run", new_callable=AsyncMock,
                    side_effect=OSError("test error")):
            result = event_loop.run_until_complete(
                internal(lambda: None, mock_console, None, True))
            assert result == 1

    def test_terminal_restored_on_exit(self, event_loop, mock_console):
        """Test that the terminal is put in raw mode and restored after exit"""
        inp = MagicMock()

        with patch("labgrid.util.term.run", new_callable=AsyncMock) as mock_run, \
             patch("labgrid.util.term.create_input", return_value=inp):
            event_loop.run_until_complete(
                internal(lambda: None, mock_console, None, False))

            # prompt_toolkit restores the previous settings on exit
            inp.raw_mode.assert_called_once()
            raw_mode = inp.raw_mode.return_value
            raw_mode.__enter__.assert_called_once()
            raw_mode.__exit__.assert_called_once()
            inp.close.assert_called_once()

            # The terminal is passed on, so that run() can watch the keyboard
            assert mock_run.await_args[0][4] is inp
