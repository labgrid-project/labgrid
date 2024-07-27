"""Terminal handling, using microcom or telnet"""

import asyncio
import logging
import sys
import shutil

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
