"""Terminal handling, using microcom, telnet or an internal function"""

import asyncio
import contextlib
import logging
import os
import sys
import shutil
import time

from pexpect import TIMEOUT
from prompt_toolkit.input import create_input
from serial.serialutil import SerialException

EXIT_CHAR = 0x1d    # FS (Ctrl + ])
EXIT_WINDOW = .5    # seconds allowed between the two exit characters
PROMPT_CHAR = 0x14  # DC4 (Ctrl + T), opens the command prompt
HELD_LIMIT = 1024 * 1024  # console output kept while the prompt is open

logger = logging.getLogger("ClientSession")


class ConsolePrompt:
    """Line editor for the console command prompt.

    feed() takes raw terminal input and returns (output, status, rest): output
    is to be written to the terminal, status is None while editing, "enter"
    (the line is in self.line), "cancel" (Ctrl-C) or "literal" (Ctrl-T, to be
    sent to the target) and rest is the input following a final status.
    Tab completes the line against the command names or lists the matches.
    Escape sequences (e.g. arrow keys) are ignored.
    """

    CONSOLE_CONTROL_PROMPT = "labgrid> "

    def __init__(self, commands):
        self.commands = sorted(commands)
        self.line = ""
        self._esc = None

    def start(self):
        self.line = ""
        self._esc = None
        return f"\r\n{self.CONSOLE_CONTROL_PROMPT}".encode()

    def feed(self, data):
        out = []
        for i, b in enumerate(data):
            status = self._key(b, out)
            if status:
                return "".join(out).encode(), status, data[i + 1 :]
        return "".join(out).encode(), None, b""

    def _key(self, b, out):
        if self._esc == "esc":
            # skip the escape sequence (CSI/SS3) or Alt+key
            self._esc = "seq" if b in b"[O" else None
        elif self._esc == "seq":
            if 0x40 <= b <= 0x7E:
                self._esc = None
        elif b == 0x1B:
            self._esc = "esc"
        elif b in b"\r\n":
            out.append("\r\n")
            return "enter"
        elif b == 0x03:
            out.append("\r\n")
            return "cancel"
        elif b == 0x14:
            out.append("\r\n")
            return "literal"
        elif b in b"\x7f\x08":
            if self.line:
                self.line = self.line[:-1]
                out.append("\b \b")
        elif b == 0x09:
            out.append(self._complete())
        elif 0x20 <= b < 0x7F:
            self.line += chr(b)
            out.append(chr(b))
        return None

    def _complete(self):
        matches = [c for c in self.commands if c.startswith(self.line)]
        prefix = os.path.commonprefix(matches)
        if len(prefix) > len(self.line):
            added = prefix[len(self.line) :]
            self.line = prefix
            return added
        if not matches:
            return "\a"
        return f"\r\n{'  '.join(matches)}\r\n{self.CONSOLE_CONTROL_PROMPT}{self.line}"


async def external(check_allowed, host, port, resource, logfile, listen_only):
    """Start an external terminal sessions

    This uses microcom if available, otherwise falls back to telnet.

    Args:
        check_allowed (lambda): Function to call to make sure the terminal is
            still accessible. No args. Returns None if allowed, else a string
            describing why access is lost
        host (str): Host name to connect to
        port (int): Port number to connect to
        resource (str): Serial resource to connect to (used to get speed / name)
        logfile (str): Logfile to write output too, or None. This is ignored if
            telnet is used
        listen_only (bool): True to ignore keyboard input (ignored with telnet)

    Returns:
        int: Return code from tool
    """
    microcom_bin = shutil.which("microcom")

    if microcom_bin is not None:
        call = [microcom_bin, "-s", str(resource.speed), "-t", f"{host}:{port}"]

        if listen_only:
            call.append("--listenonly")

        if logfile:
            call.append(f"--logfile={logfile}")
    else:
        call = ["telnet", host, str(port)]

        logger.info("microcom not available, using telnet instead")

        if listen_only:
            logger.warning("--listenonly option not supported by telnet, ignoring")

        if logfile:
            logger.warning("--logfile option not supported by telnet, ignoring")

    logger.info("connecting to %s calling %s", resource, " ".join(call))
    p = await asyncio.create_subprocess_exec(*call)
    while p.returncode is None:
        try:
            await asyncio.wait_for(p.wait(), 1.0)
        except asyncio.TimeoutError:
            # subprocess is still running
            pass

        if check_allowed():
            p.terminate()
            try:
                await asyncio.wait_for(p.wait(), 1.0)
            except asyncio.TimeoutError:
                # try harder
                p.kill()
                await asyncio.wait_for(p.wait(), 1.0)
            break
    if p.returncode:
        print("connection lost", file=sys.stderr)
    return p.returncode


BUF_SIZE = 1024

async def run(check_allowed, cons, log_fd, listen_only, inp=None, commands=None):
    """Handle the console session, passing data between board and terminal

    If commands is given, Ctrl-T opens a command prompt (see ConsolePrompt).
    Console output is held back while it is open. Ctrl-T Ctrl-T sends a
    literal Ctrl-T to the board.

    Args:
        check_allowed (lambda): Function to call to make sure the terminal is
            still accessible. No args. Returns None if allowed, else a string
            describing why access is lost
        cons (ConsoleProtocol): Console device to read/write
        log_fd (file): File to write console output to, or None
        listen_only (bool): True to ignore keyboard input
        inp (prompt_toolkit Input): Terminal to read keystrokes from, or None
            to ignore the keyboard
        commands (tuple): (names, handler) for the command prompt, or None
            for no prompt. names is a list of command lines for Tab
            completion. handler is called with the line entered and returns
            a message to show, or a function to run the command, which
            returns a message to show or None. The function is called in
            this thread, since labgrid steps are not thread-safe, so the
            console is not read until it returns

    Returns:
        int: 0 if the session ended normally, 1 if the console was lost
    """
    returncode = 0
    exit_deadline = None
    to_cons = b''
    next_cons = time.monotonic()
    txdelay = cons.txdelay
    txchunk = getattr(cons, 'txchunk', 1)
    typed = bytearray()
    prompt = ConsolePrompt([*commands[0], "q"]) if commands and inp else None
    prompting = False
    held = bytearray()
    dropped = False

    def write(data):
        nonlocal dropped
        if prompting:
            dropped |= len(held) + len(data) > HELD_LIMIT
            held.extend(data[:HELD_LIMIT - len(held)])
        else:
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()

    def say(msg):
        msg = msg.rstrip("\n").replace("\n", "\r\n")
        write(f"\r\n[labgrid] {msg}\r\n".encode())

    def leave_prompt():
        nonlocal prompting, dropped
        prompting = False
        write(bytes(held))
        held.clear()
        if dropped:
            say("some console output was dropped while the prompt was open")
            dropped = False

    def run_command(line):
        line = " ".join(line.split())
        # Enter already closed the prompt, so there is nothing left to do for q
        if line in ("", "q"):
            return
        try:
            res = commands[1](line)
            if callable(res):
                say(f"{line}...")
                res = res() or f"{line} done"
        except Exception as e:  # pylint: disable=broad-except
            res = f"{line} failed: {e}"
        if res:
            say(res)

    def read_keys():
        """Collect what the user types, called by the event loop

        This reads the bytes as they arrive, rather than using prompt_toolkit's
        read_keys(), since the board needs a transparent stream: it must see
        escape sequences and control characters exactly as they were typed.
        """
        try:
            data = os.read(inp.fileno(), BUF_SIZE)
        except OSError:
            data = b''
        if data:
            typed.extend(data)
        else:
            # The terminal is gone (e.g. a closed pipe), so stop watching it,
            # else the event loop calls us forever
            asyncio.get_running_loop().remove_reader(inp.fileno())

    # Show a message to indicate we are waiting for output from the board
    if prompt:
        msg = 'Terminal ready...press Ctrl-] twice to exit, Ctrl-T for commands'
    elif inp:
        msg = 'Terminal ready...press Ctrl-] twice to exit'
    else:
        msg = 'Terminal ready...press Ctrl-C to exit'
    sys.stdout.write(msg)
    sys.stdout.flush()
    erase_msg = '\b' * len(msg) + ' ' * len(msg) + '\b' * len(msg)
    have_output = False

    # Ask the event loop to tell us when the user types something
    watch_keys = inp.attach(read_keys) if inp else contextlib.nullcontext()

    with watch_keys:
        while True:
            activity = bool(to_cons)
            try:
                data = cons.read(size=BUF_SIZE, timeout=0.001)
                if data:
                    activity = True
                    if not have_output:
                        # Erase our message
                        sys.stdout.write(erase_msg)
                        sys.stdout.flush()
                        have_output = True
                    write(data)
                    if log_fd:
                        log_fd.write(data)
                        log_fd.flush()

            except TIMEOUT:
                pass

            except SerialException:
                returncode = 1
                break

            # A lone exit character is meant for the board, so send it on
            if exit_deadline and time.monotonic() > exit_deadline:
                to_cons += bytes([EXIT_CHAR])
                exit_deadline = None

            if typed:
                data = bytes(typed)
                typed.clear()
                activity = True

                # Hold back an exit character until we know whether a second
                # one follows; if it does, exit without sending either
                done = False
                out = bytearray()
                while data:
                    if prompting:
                        echo, status, data = prompt.feed(data)
                        sys.stdout.buffer.write(echo)
                        sys.stdout.buffer.flush()
                        if status == "literal":
                            out.append(PROMPT_CHAR)
                        if status:
                            leave_prompt()
                        if status == "enter":
                            run_command(prompt.line)
                        continue
                    ch, data = data[0], data[1:]
                    if ch == EXIT_CHAR and exit_deadline:
                        done = True
                        break
                    if exit_deadline:
                        out.append(EXIT_CHAR)
                        exit_deadline = None
                    if ch == EXIT_CHAR:
                        exit_deadline = time.monotonic() + EXIT_WINDOW
                    elif ch == PROMPT_CHAR and prompt:
                        prompting = True
                        # the prompt goes below our message, so leave it there
                        have_output = True
                        sys.stdout.buffer.write(prompt.start())
                        sys.stdout.buffer.flush()
                    else:
                        out.append(ch)
                if done:
                    break

                to_cons += bytes(out)

            # Send txchunk bytes at a time, with txdelay between chunks. Time
            # the delay from the last write, so that the board still gets
            # the delay after the console has been idle
            if to_cons and time.monotonic() >= next_cons:
                if txdelay:
                    cons._write(to_cons[:txchunk])
                    to_cons = to_cons[txchunk:]
                    next_cons = time.monotonic() + txdelay
                else:
                    cons._write(to_cons)
                    to_cons = b''

            if check_allowed():
                break

            # Give the event loop a chance to run read_keys()
            await asyncio.sleep(0 if activity else .001)

    if prompting:
        leave_prompt()

    # Blank line to move past any partial output
    print()
    if returncode:
        print("connection lost", file=sys.stderr)
    return returncode


async def internal(check_allowed, cons, logfile, listen_only, commands=None):
    """Start an internal terminal session

    This talks to the board directly, rather than starting a separate tool.

    Args:
        check_allowed (lambda): Function to call to make sure the terminal is
            still accessible. No args. Returns None if allowed, else a string
            describing why access is lost
        cons (ConsoleProtocol): Console device to read/write
        logfile (str): Logfile to write output too, or None
        listen_only (bool): True to ignore keyboard input
        commands (tuple): Commands for the command prompt, see run()

    Return:
        int: Result code
    """
    returncode = 0
    log_fd = None
    inp = None
    try:
        # Watch the keyboard, unless we only care about what the board says
        if not listen_only:
            inp = create_input()

        if logfile:
            log_fd = open(logfile, 'wb')

        logger.info('Console start:')

        # Put the terminal in raw mode, so that keystrokes reach the board
        # untouched.  As well as the echo and line editing, this turns off
        # flow control (so that Ctrl-S and Ctrl-Q get through) and the
        # carriage-return translation.  It does nothing if stdin is not a
        # terminal, such as when input is piped in
        raw_mode = inp.raw_mode() if inp else contextlib.nullcontext()
        with raw_mode:
            returncode = await run(check_allowed, cons, log_fd, listen_only, inp, commands)

    except OSError as err:
        print('error', err)
        returncode = 1

    finally:
        if inp:
            inp.close()
        if log_fd:
            log_fd.close()

    return returncode
