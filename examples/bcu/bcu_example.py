import pytest


@pytest.fixture()
def switchcfg(target):
    # bcu tool needs to be installed on workstation
    return target.get_driver('BCUResetDriver')

@pytest.fixture()
def shell(target):
    s = target.get_driver('ShellDriver')
    #in case board remained booted from a different test
    target.deactivate(s)
    return s

@pytest.mark.lg_feature("SDcard")
def test_boot_from_sdcard(target, switchcfg, shell):
    # Note that you need a bootable image already on sd
    switchcfg.sd()
    try:
        target.activate(shell)
    except:
        assert False, "Board failed to boot"
    stdout, stderr, returncode = shell.run('dmesg | grep root=/dev/mmcblk1')
    assert returncode == 0, "Board booted from wrong environment"

def test_boot_from_emmc(target, switchcfg, shell):
    # Note that you need a bootable image already on emmc
    switchcfg.emmc()
    try:
        target.activate(shell)
    except:
        assert False, "Board failed to boot"
    stdout, stderr, returncode = shell.run('dmesg | grep root=/dev/mmcblk0')
    assert returncode == 0, "Board booted from wrong environment"

