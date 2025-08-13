import pytest
import subprocess
import tempfile
import attr
import os
from pathlib import Path
from labgrid.driver.flashscriptdriver import FlashScriptDriver
from labgrid.resource.common import ManagedResource
from labgrid import target_factory


@target_factory.reg_resource
@attr.s(eq=False)
class MockFlashableDevice(ManagedResource):
    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.avail = True

    @property
    def prop(self):
        return "test"


@pytest.fixture(scope="function")
def resource(target):
    r = MockFlashableDevice(target, name=None)
    assert isinstance(r, MockFlashableDevice)
    target.activate(r)
    return r


@pytest.fixture(scope="function")
def driver(target, mocker, resource):
    mocker.patch.dict(
        FlashScriptDriver.bindings,
        {
            "device": {
                "MockFlashableDevice",
            },
        },
    )

    d = FlashScriptDriver(target, name=None)
    assert isinstance(d, FlashScriptDriver)
    target.activate(d)
    return d


def capture_argument_expansion(d, var):
    with tempfile.NamedTemporaryFile() as f:
        d.flash("/bin/sh", args=["-c", "echo -n {%s} > %s" % (var, f.name)])
        return f.read().decode("utf-8")


@pytest.mark.skipif(not Path("/bin/true").exists(), reason="true not available")
def test_script_success(target, driver):
    driver.flash("/bin/true")


@pytest.mark.skipif(not Path('/bin/false').exists(), reason="false not available")
def test_script_failure(target, driver):
    with pytest.raises(subprocess.CalledProcessError):
        driver.flash("/bin/false")


def test_argument_device_expansion(target, resource, driver):
    value = capture_argument_expansion(driver, "device.prop")
    assert value == resource.prop


def test_argument_file_expansion(target, driver):
    value = capture_argument_expansion(driver, "file.local_path")
    assert os.path.samefile(value, "/bin/sh")
