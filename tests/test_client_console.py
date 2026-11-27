import os
import sys
import textwrap

import pexpect

# pexpect does not answer prompt_toolkit's cursor position requests
ENV = {**os.environ, "PROMPT_TOOLKIT_NO_CPR": "1"}

SCRIPT = textwrap.dedent("""
    import asyncio
    import os
    import sys
    from types import SimpleNamespace
    from labgrid.remote.client import ClientSession

    class Power:
        state = False
        delay = 2.0
        def on(self): self.state = True
        def off(self): self.state = False
        def cycle(self): self.state = True
        def get(self): return self.state

    class Session:
        _console_pty = ClientSession._console_pty
        _console_commands = ClientSession._console_commands
        _power = ClientSession._power
        power = Power()
        def _get_power_driver(self, target, name=None):
            return self.power

    async def main():
        place = SimpleNamespace(name="test")
        keep_prompt = "KEEP_PROMPT" in os.environ
        with Session()._console_pty(place, None, sys.argv[1:], keep_prompt=keep_prompt) as (call, kwargs):
            p = await asyncio.create_subprocess_exec(*call, **kwargs)
            print("ready", flush=True)
            await p.wait()

    asyncio.run(main())
""")


def prompt(spawn, keys):
    """Open the command prompt and type keys into it

    The prompt is drawn by prompt_toolkit with escape sequences in between,
    so tests only look for "labgrid>" and for the plain messages printed
    after it is closed.
    """
    spawn.send("\x14")
    spawn.expect("labgrid>")
    spawn.send(keys)


def test_console_pty_commands():
    with pexpect.spawn(sys.executable, ["-c", SCRIPT, "cat"], env=ENV, timeout=10) as spawn:
        spawn.expect("ready")
        spawn.send("hello\r")
        spawn.expect("hello")
        # Tab completion and running a command
        prompt(spawn, "power g")
        # completions are computed asynchronously, so wait for the menu
        spawn.expect("get")
        spawn.send("\t")
        spawn.expect("et")
        spawn.send("\r")
        spawn.expect(r"\[labgrid\] power for place test is off")
        prompt(spawn, "power on\r")
        spawn.expect(r"\[labgrid\] power on done")
        prompt(spawn, "power get\r")
        spawn.expect(r"\[labgrid\] power for place test is on")
        # pw is short for power, like for labgrid-client
        prompt(spawn, "pw of")
        spawn.expect("off")
        spawn.send("\t")
        spawn.expect("f")
        spawn.send("\r")
        spawn.expect(r"\[labgrid\] pw off done")
        prompt(spawn, " pw  get \r")
        spawn.expect(r"\[labgrid\] power for place test is off")
        # options and errors come from the labgrid-client argument parser
        prompt(spawn, "pw cycle -t 0.5\r")
        spawn.expect(r"\[labgrid\] pw cycle -t 0.5 done")
        prompt(spawn, "pw onn\r")
        spawn.expect(r"\[labgrid\] usage: power .*\r\npower: error: argument action: invalid choice: 'onn'")
        prompt(spawn, "help\r")
        spawn.expect(
            r"\[labgrid\] usage: power \[-h\] \[-t DELAY\] \[--name NAME\] \{on,off,cycle,get\}\r\n  \(short: pw\)"
        )
        prompt(spawn, "nope\r")
        spawn.expect(r"\[labgrid\] unknown command 'nope'")
        # q leaves the prompt, then input goes to the target again. Wait for
        # prompt_toolkit to finish, else it keeps what is typed meanwhile.
        prompt(spawn, "q\r")
        spawn.expect_exact("\x1b[?2004l")
        spawn.send("world\r")
        spawn.expect("world\r\nworld")
        # Ctrl-T Ctrl-T sends a literal Ctrl-T, echoed back by the pty, also
        # when the second one is read by the prompt
        spawn.send("\x14\x14")
        spawn.expect_exact("^T")
        prompt(spawn, "\x14")
        spawn.expect_exact("^T")
        # EOF through the pty ends cat
        spawn.send("\r\x04")
        spawn.expect(pexpect.EOF)
    assert spawn.exitstatus == 0


def test_console_pty_hold_output():
    with pexpect.spawn(
        sys.executable,
        ["-c", SCRIPT, "sh", "-c", r"sleep 1; printf 'late\033[6n\033[18t!\n'; sleep 2"],
        env=ENV,
        timeout=10,
    ) as spawn:
        spawn.expect("ready")
        prompt(spawn, "")
        # output is held back while the prompt is open ...
        assert spawn.expect(["late", pexpect.TIMEOUT], timeout=2) == 1
        # ... and shown after leaving it with Ctrl-C, without terminal queries
        spawn.send("\x03")
        spawn.expect_exact("late!")
        spawn.expect(pexpect.EOF)
    assert spawn.exitstatus == 0


def test_console_pty_ctty():
    # /dev/tty can only be opened with a controlling terminal
    prog = [sys.executable, "-c", "open('/dev/tty'); print('has ctty')"]
    with pexpect.spawn(sys.executable, ["-c", SCRIPT, *prog], env=ENV, timeout=10) as spawn:
        spawn.expect("has ctty")
        spawn.expect(pexpect.EOF)
    assert spawn.exitstatus == 0


def test_console_pty_keep_prompt():
    with pexpect.spawn(
        sys.executable,
        ["-c", SCRIPT, "sh", "-c", "sleep 1; echo late; exec cat"],
        env={**ENV, "KEEP_PROMPT": "1"},
        timeout=10,
    ) as spawn:
        spawn.expect("ready")
        prompt(spawn, "pw on\r")
        spawn.expect(r"\[labgrid\] pw on done")
        # the prompt stays open for the next command, also after an empty line
        spawn.expect("labgrid>")
        spawn.send("\r")
        spawn.expect("labgrid>")
        spawn.send("pw get\r")
        spawn.expect(r"\[labgrid\] power for place test is on")
        spawn.expect("labgrid>")
        # output is still held back until q leaves the prompt
        assert spawn.expect(["late", pexpect.TIMEOUT], timeout=2) == 1
        spawn.send("q\r")
        spawn.expect_exact("\x1b[?2004l")
        spawn.expect("late")
        spawn.send("hello\r")
        spawn.expect("hello\r\nhello")
        # Ctrl-C leaves it as well
        prompt(spawn, "\x03")
        spawn.expect_exact("\x1b[?2004l")
        spawn.send("world\r")
        spawn.expect("world\r\nworld")
        spawn.send("\x04")
        spawn.expect(pexpect.EOF)
    assert spawn.exitstatus == 0
