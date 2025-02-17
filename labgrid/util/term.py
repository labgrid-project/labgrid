"""Terminal handling, using microcom, telnet or an internal function"""

import asyncio
import collections
import logging
import os
import sys
import shutil
import termios
import time

from pexpect import TIMEOUT
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
    logging.info("connecting to %s calling %s", resource, ' '.join(call))
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

async def run(check_allowed, cons, log_fd, listen_only):
    prev = collections.deque(maxlen=2)

    deadline = None
    to_cons = b''
    next_cons = time.monotonic()
    txdelay = cons.txdelay

    # Show a message to indicate we are waiting for output from the board
    msg = 'Terminal ready...press Ctrl-] twice to exit'
    sys.stdout.write(msg)
    sys.stdout.flush()
    erase_msg = '\b' * len(msg) + ' ' * len(msg) + '\b' * len(msg)
    have_output = False

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

        if not listen_only:
            data = os.read(sys.stdin.fileno(), BUF_SIZE)
            if data:
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
        if not activity:
            time.sleep(.001)

    # Blank line to move past any partial output
    print()


async def internal(check_allowed, cons, logfile, listen_only):
    """Start an external terminal sessions

    This uses microcom if available, otherwise falls back to telnet.

    Args:
        check_allowed (lambda): Function to call to make sure the terminal is
            still accessible. No args. Returns True if allowed, False if not.
        cons (str): ConsoleProtocol device to read/write
        logfile (str): Logfile to write output too, or None
        listen_only (bool): True to ignore keyboard input

    Return:
        int: Result code
    """
    returncode = 0
    old = None
    try:
        if not listen_only and os.isatty(sys.stdout.fileno()):
            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            new = termios.tcgetattr(fd)
            new[3] = new[3] & ~(termios.ICANON | termios.ECHO | termios.ISIG)
            new[6][termios.VMIN] = 0
            new[6][termios.VTIME] = 0
            termios.tcsetattr(fd, termios.TCSANOW, new)

        log_fd = None
        if logfile:
            log_fd = open(logfile, 'wb')

        logging.info('Console start:')
        await run(check_allowed, cons, log_fd, listen_only)

    except OSError as err:
        print('error', err)
        returncode = 1

    finally:
        if old:
            termios.tcsetattr(fd, termios.TCSAFLUSH, old)
        if log_fd:
            log_fd.close()

    return returncode
