import os

import pytest

WORKDIR = os.path.join("~", "workspace", "zephyrproject")


@pytest.fixture(scope="session", autouse=True)
def bootstrap(target):
    power = target.get_driver("USBPowerDriver")
    power.on()

    t32 = target.get_driver("BootstrapProtocol")
    t32.load(filename=os.path.join(WORKDIR, "zephyr", "build", "zephyr", "zephyr.elf"))


@pytest.fixture(scope="function")
def shell(target):
    shell = target.get_driver("SerialDriver")
    return shell


def test_boot_status(target, shell):
    """Check boot status"""

    power = target.get_driver("USBPowerDriver")
    power.cycle()

    shell.expect(r"\*\*\* Booting Zephyr OS", timeout=5.0)
