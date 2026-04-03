"""Tests for labgrid.util.term — terminal handling"""

import asyncio
import io
import logging
import os
import sys
import termios
import threading
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from labgrid.util.term import external, run, internal, EXIT_CHAR
from pexpect import TIMEOUT
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
        txdelay: per-byte transmit delay in seconds
        on_write: optional callback invoked with each byte written
    """
    def __init__(self, txdelay=0, on_write=None):
        self.txdelay = txdelay
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
    """Create a pipe and yield (read_file, write_fd).

    The read side is wrapped in a file object suitable for patching
    sys.stdin.  Both ends are closed on cleanup.
    """
    read_fd, write_fd = os.pipe()
    read_file = os.fdopen(read_fd, 'rb', 0)
    yield read_file, write_fd
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
    def test_exit_on_double_ctrl_bracket(self, event_loop, mock_console):
        """Test that double Ctrl+] exits the loop"""
        exit_data = bytes([EXIT_CHAR, EXIT_CHAR])
        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = 0

        with patch("os.read", return_value=exit_data), \
             patch("sys.stdin", mock_stdin), \
             patch("sys.stdout", new_callable=lambda: MagicMock(spec=sys.stdout)):
            event_loop.run_until_complete(
                run(lambda: None, mock_console, None, False))

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

    def test_serial_exception_exits(self, event_loop, mock_console):
        """Test that SerialException breaks out of the loop"""
        mock_console.read = MagicMock(side_effect=SerialException("disconnected"))

        with patch("sys.stdout", new_callable=lambda: MagicMock(spec=sys.stdout)):
            event_loop.run_until_complete(
                run(lambda: None, mock_console, None, True))

    def test_stdin_written_to_console(self, event_loop, stdin_pipe):
        """Test that stdin data is written to the console one byte at a time,
        using a pipe for stdin rather than mocking os.read"""
        read_file, write_fd = stdin_pipe
        os.write(write_fd, b"Hi")
        os.close(write_fd)

        cons = FakeConsole()

        # os.read on a pipe returns b"" at EOF, which is falsy, so
        # the loop will just keep going.  Exit once both bytes are written.
        def check():
            return "done" if len(cons.written) >= 2 else None

        with patch("sys.stdin", read_file), \
             patch("sys.stdout", new_callable=lambda: MagicMock(spec=sys.stdout)):
            event_loop.run_until_complete(
                run(check, cons, None, False))

        assert cons.written == [b"H", b"i"]

    def test_stdin_txdelay(self, event_loop, stdin_pipe):
        """Test that txdelay throttles bytes written to the console"""
        read_file, write_fd = stdin_pipe
        os.write(write_fd, b"AB")
        os.close(write_fd)

        timestamps = []
        def record_time(data):
            timestamps.append(time.monotonic())

        cons = FakeConsole(txdelay=0.05, on_write=record_time)

        def check():
            return "done" if len(timestamps) >= 2 else None

        with patch("sys.stdin", read_file), \
             patch("sys.stdout", new_callable=lambda: MagicMock(spec=sys.stdout)):
            event_loop.run_until_complete(
                run(check, cons, None, False))

        assert len(timestamps) == 2
        gap = timestamps[1] - timestamps[0]
        # Allow 10ms margin below the 50ms txdelay for scheduling jitter
        assert gap >= 0.04

    def test_exit_char_deadline_resets(self, event_loop, stdin_pipe):
        """Test that a single Ctrl+] is forgotten after the 0.5s deadline.

        Send Ctrl+] then wait for the deadline to expire, then send
        normal data.  The normal data should be written to the console
        (proving the exit-char was cleared) rather than combined with
        the stale Ctrl+] to trigger exit.

        To avoid a brittle fixed sleep, the feeder thread uses a
        threading.Event set by _write() when the Ctrl+] byte arrives.
        This way the 0.6s deadline-expiry sleep only starts once we
        know the loop has processed the keystroke and set its internal
        deadline, removing any race between the pipe write and the
        main loop.
        """
        read_file, write_fd = stdin_pipe
        got_exit_char = threading.Event()

        def on_write(data):
            if data == bytes([EXIT_CHAR]):
                got_exit_char.set()

        cons = FakeConsole(on_write=on_write)

        def feed_stdin():
            os.write(write_fd, bytes([EXIT_CHAR]))
            # Wait until the loop has processed the Ctrl+] (deadline is set)
            got_exit_char.wait(timeout=5)
            time.sleep(0.6)  # exceed the 0.5s deadline
            os.write(write_fd, b"X")
            os.close(write_fd)

        threading.Thread(target=feed_stdin, daemon=True).start()

        # Safety: also exit after 3s in case the feeder thread fails
        start = time.monotonic()
        def check():
            if time.monotonic() - start > 3:
                return "timeout"
            return "done" if any(d == b"X" for d in cons.written) else None

        with patch("sys.stdin", read_file), \
             patch("sys.stdout", new_callable=lambda: MagicMock(spec=sys.stdout)):
            event_loop.run_until_complete(
                run(check, cons, None, False))

        assert b"X" in cons.written

    def test_check_allowed_exits(self, event_loop, mock_console):
        """Test that check_allowed returning truthy exits the loop"""
        with patch("sys.stdout", new_callable=lambda: MagicMock(spec=sys.stdout)):
            event_loop.run_until_complete(
                run(lambda: "not allowed", mock_console, None, True))


# --- internal() tests ---

class TestInternal:
    def test_listen_only_no_termios(self, event_loop, mock_console):
        """Test that listen_only mode skips terminal setup"""
        with patch("labgrid.util.term.run", new_callable=AsyncMock) as mock_run, \
             patch("labgrid.util.term.termios") as mock_termios:
            result = event_loop.run_until_complete(
                internal(lambda: None, mock_console, None, True))

            mock_termios.tcgetattr.assert_not_called()
            mock_run.assert_awaited_once()
            assert result == 0

    def test_with_logfile(self, event_loop, mock_console, tmp_path):
        """Test that a logfile is opened and closed"""
        logfile = str(tmp_path / "test.log")

        with patch("labgrid.util.term.run", new_callable=AsyncMock):
            result = event_loop.run_until_complete(
                internal(lambda: None, mock_console, logfile, True))

            assert result == 0
            assert os.path.exists(logfile)

    def test_os_error_returns_1(self, event_loop, mock_console):
        """Test that OSError during run returns exitcode 1"""
        with patch("labgrid.util.term.run", new_callable=AsyncMock,
                    side_effect=OSError("test error")):
            result = event_loop.run_until_complete(
                internal(lambda: None, mock_console, None, True))
            assert result == 1

    def test_terminal_restored_on_exit(self, event_loop, mock_console):
        """Test that terminal attributes are restored after exit"""
        old_attrs = [0, 0, 0, 0, 0, 0, [0] * 32]

        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = 0

        with patch("labgrid.util.term.run", new_callable=AsyncMock), \
             patch("labgrid.util.term.os.isatty", return_value=True), \
             patch("labgrid.util.term.sys.stdin", mock_stdin), \
             patch("labgrid.util.term.termios.tcgetattr", return_value=old_attrs.copy()), \
             patch("labgrid.util.term.termios.tcsetattr") as mock_set:
            event_loop.run_until_complete(
                internal(lambda: None, mock_console, None, False))

            assert mock_set.call_count == 2
            # First call: setup (TCSANOW), second call: restore (TCSAFLUSH)
            setup_call = mock_set.call_args_list[0]
            assert setup_call[0][1] == termios.TCSANOW
            restore_call = mock_set.call_args_list[1]
            assert restore_call[0][1] == termios.TCSAFLUSH
            assert restore_call[0][2] == old_attrs
