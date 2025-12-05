import csv

import pytest


@pytest.fixture(scope="session")
def rcl(target):
    t32 = target.get_driver("LauterbachDriver")

    rcl_ = t32.control()
    while rcl_._get_practice_state():
        pass

    return rcl_


def test_stack(rcl):
    """Check maximum stack consumption"""

    rcl.cmd("Break")
    rcl.cmd("WAIT 1.0s")

    file = "stack.csv"
    rcl.cmd(f'PRinTer.FILE "{file}" CSV')
    rcl.cmd("WinPrint.TASK.STacK.view")

    with open(file, "r") as f:
        reader = csv.reader(f)
        for ii, row in enumerate(reader):
            if ii <= 1:
                continue

            max = int(row[7].replace("%", ""))
            assert max < 40, f'Task "{row[0]}" consumes too much stack ({max}%). Aborting...'


def test_ramdump(rcl):
    """Force panic and generate ramdump"""

    rcl.cmd("Go")
    rcl.cmd('TERM.OUT "PANIC" 0xa')
    rcl.cmd("WAIT 1.0s")

    rcl.cmd("Break")
    rcl.cmd("WAIT 1.0s")

    file = "frame.csv"
    rcl.cmd(f'PRinTer.FILE "{file}" CSV')
    rcl.cmd("WinPrint.Frame")

    with open(file, "r") as f:
        reader = csv.reader(f)
        panicked = False
        for ii, row in enumerate(reader):
            if ii <= 0:
                continue

            if len(row) > 1 and "k_sys_fatal_error_handler" in row[1]:
                panicked = True
                break

    assert panicked, "No fatal kernel error detected."

    rcl.cmd('DO ~~/demo/arm/kernel/zephyr/v3.x/ramdump.cmm MEM="AD:0x0--0xffff,AD:0x20000000++0xfff"')
    while rcl._get_practice_state():
        pass
