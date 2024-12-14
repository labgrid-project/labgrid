from pexpect.exceptions import TIMEOUT
import pytest
import subprocess
import sys

@pytest.fixture
def u_boot(target, strategy):
    try:
        strategy.transition("uboot")
    except subprocess.CalledProcessError as exc:
        # Show any build failures
        print(f"Command failure: {' '.join(exc.cmd)}")
        for line in exc.output.splitlines():
            print(line.decode('utf-8'))
    except TIMEOUT:
        # Show any console output when things fail
        console = target.get_active_driver('ConsoleProtocol')
        output = console.read_output()
        sys.stdout.buffer.write(output)
        raise
    return strategy.uboot
