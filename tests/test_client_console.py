import sys
import textwrap

import pexpect


SCRIPT = textwrap.dedent("""
    import asyncio
    import sys
    from labgrid.remote.client import ClientSession

    class Session:
        _console_pty = ClientSession._console_pty

    async def main():
        with Session()._console_pty(sys.argv[1:]) as (call, kwargs):
            p = await asyncio.create_subprocess_exec(*call, **kwargs)
            print("ready", flush=True)
            await p.wait()

    asyncio.run(main())
""")


def test_console_pty():
    with pexpect.spawn(sys.executable, ["-c", SCRIPT, "cat"], timeout=10) as spawn:
        spawn.expect("ready")
        spawn.send("hello\r")
        spawn.expect("hello")
        # EOF through the pty ends cat
        spawn.send("\x04")
        spawn.expect(pexpect.EOF)
    assert spawn.exitstatus == 0


def test_console_pty_ctty():
    # /dev/tty can only be opened with a controlling terminal
    prog = [sys.executable, "-c", "open('/dev/tty'); print('has ctty')"]
    with pexpect.spawn(sys.executable, ["-c", SCRIPT, *prog], timeout=10) as spawn:
        spawn.expect("has ctty")
        spawn.expect(pexpect.EOF)
    assert spawn.exitstatus == 0
