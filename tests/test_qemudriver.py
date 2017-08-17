import pytest

from labgrid.driver import QEMUDriver
from labgrid import Environment

@pytest.fixture
def qemu_env(tmpdir):
    p = tmpdir.join("config.yaml")
    p.write(
        """
        targets:
          main:
            role: foo
        images:
          kernel: "test.zImage"
          dtb: test.dtb"
        tools:
          qemu: "qemu-system-arm"
        paths:
          rootfs: "test/path"
        """
    )
    return Environment(str(p))

@pytest.fixture
def qemu_target(qemu_env):
    return qemu_env.get_target()

@pytest.fixture
def qemu_driver(qemu_target):
    q = QEMUDriver(
        qemu_target,
        "qemu",
        qemu_bin="qemu",
        machine='',
        cpu='',
        memory='',
        boot_args='',
        extra_args='',
        kernel='kernel',
        rootfs='rootfs')
    return q

def test_qemu_instance(qemu_target, qemu_driver):
    assert (isinstance(qemu_driver, QEMUDriver))

def test_qemu_activate_deactivate(qemu_target, qemu_driver):
    qemu_target.activate(qemu_driver)
    qemu_target.deactivate(qemu_driver)
