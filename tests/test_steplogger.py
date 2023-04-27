import pexpect
import pytest
import time
import re

@pytest.fixture
def power_env(tmpdir):
    p = tmpdir.join("config.yaml")
    p.write(
"""
targets:
  main:
    drivers:
      ManualPowerDriver: {}
"""
    )
    return p

@pytest.fixture
def pw_cycle_test(tmpdir):
    t = tmpdir.join("pw_cycle_test.py")
    t.write(
"""
def test(target):
    pw = target.get_driver("ManualPowerDriver")
    pw.cycle()
"""
    )
    return t

def test_step_logger(power_env, pw_cycle_test):
    from colors import strip_color
    # step reporter is called when -vv is given
    # -s is necessary for manual power driver confirmation
    with pexpect.spawn('pytest -vvs --lg-env {env} {test}'
                       .format(env=power_env, test=pw_cycle_test)) as spawn:

        # rough match
        spawn.expect("→.*?ManualPowerDriver.*?cycle.*?\r\n".encode("utf-8"))
        step_line = strip_color(spawn.after.decode("utf-8")).rstrip()
        # exact match
        assert step_line.endswith("→ ManualPowerDriver.cycle()"), f"'{step_line}' did not match"

        spawn.expect("main: CYCLE the target main and press enter")
        time.sleep(0.02) # ensure that the step measures a duration
        spawn.sendline()

        # rough match
        spawn.expect("←.*?ManualPowerDriver.*?cycle.*?\r\n".encode("utf-8"))
        step_line = strip_color(spawn.after.decode("utf-8")).rstrip()
        # exact match

        assert re.match(r"← ManualPowerDriver.cycle\(\) \[[\d.]+s\]$", step_line), f"'{step_line}' did not match"

        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0

