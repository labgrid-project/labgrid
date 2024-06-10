"""Terminal handling, using microcom, telnet or an internal function"""

import asyncio
import collections
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

async def external(check_allowed, host, port, resource, logfile, listen_only):
    """Start an external terminal sessions

    This uses microcom if available, otherwise falls back to telnet.

    Args:
        check_allowed (lambda): Function to call to make sure the terminal is
            still accessible. No args. Returns True if allowed, False if not.
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

        logging.info("microcom not available, using telnet instead")

        if listen_only:
            logging.warning("--listenonly option not supported by telnet, ignoring")

        if logfile:
            logging.warning("--logfile option not supported by telnet, ignoring")

    if logfile:
        call.append(f"--logfile={logfile}")
    logging.info("connecting to %s calling %s", resource, " ".join(call))
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

async def run(check_allowed, cons, log_fd, listen_only, inp=None):
    """Handle the console session, passing data between board and terminal

    Args:
        check_allowed (lambda): Function to call to make sure the terminal is
            still accessible. No args. Returns True if allowed, False if not.
        cons (ConsoleProtocol): Console device to read/write
        log_fd (file): File to write console output to, or None
        listen_only (bool): True to ignore keyboard input
        inp (prompt_toolkit Input): Terminal to read keystrokes from, or None
            to ignore the keyboard
    """
    prev = collections.deque(maxlen=2)

    deadline = None
    to_cons = b''
    next_cons = time.monotonic()
    txdelay = cons.txdelay
    typed = bytearray()

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
    msg = 'Terminal ready...press Ctrl-] twice to exit'
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
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()
                    if log_fd:
                        log_fd.write(data)
                        log_fd.flush()

            except TIMEOUT:
                pass

            except SerialException:
                break

            if typed:
                data = bytes(typed)
                typed.clear()
                activity = True
                if not deadline:
                    deadline = time.monotonic() + .5  # seconds
                prev.extend(data)
                count = prev.count(EXIT_CHAR)
                if count == 2:
                    break

                to_cons += data

            if to_cons and time.monotonic() > next_cons:
                cons._write(to_cons[:1])
                to_cons = to_cons[1:]
                if txdelay:
                    next_cons += txdelay

            if deadline and time.monotonic() > deadline:
                prev.clear()
                deadline = None
            if check_allowed():
                break

            # Give the event loop a chance to run read_keys()
            await asyncio.sleep(0 if activity else .001)

    # Blank line to move past any partial output
    print()


async def internal(check_allowed, cons, logfile, listen_only):
    """Start an internal terminal session

    This talks to the board directly, rather than starting a separate tool.

    Args:
        check_allowed (lambda): Function to call to make sure the terminal is
            still accessible. No args. Returns True if allowed, False if not.
        cons (ConsoleProtocol): Console device to read/write
        logfile (str): Logfile to write output too, or None
        listen_only (bool): True to ignore keyboard input

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

        logging.info('Console start:')

        # Put the terminal in raw mode, so that keystrokes reach the board
        # untouched.  As well as the echo and line editing, this turns off
        # flow control (so that Ctrl-S and Ctrl-Q get through) and the
        # carriage-return translation.  It does nothing if stdin is not a
        # terminal, such as when input is piped in
        raw_mode = inp.raw_mode() if inp else contextlib.nullcontext()
        with raw_mode:
            await run(check_allowed, cons, log_fd, listen_only, inp)

    except OSError as err:
        print('error', err)
        returncode = 1

    finally:
        if inp:
            inp.close()
        if log_fd:
            log_fd.close()

    return returncode
