import subprocess

import pytest

from labgrid.driver import ExecutionError, USBStorageDriver
from labgrid.driver.usbstoragedriver import Mode
from labgrid.resource.udev import USBMassStorage


class FakeDevice:
    """Fake block device to use for testing"""

    device_node = "/dev/sdx"
    properties = {}


@pytest.fixture
def storage(target, mocker):
    """Create an active USBStorageDriver, with its device ready to write"""
    res = USBMassStorage(target, name=None)
    res.device = FakeDevice()
    drv = USBStorageDriver(target, name=None)
    drv.WAIT_FOR_MEDIUM_TIMEOUT = 0.5
    drv.WAIT_FOR_MEDIUM_SLEEP = 0.01
    target.activate(drv)
    mocker.patch.object(drv, "get_size", return_value=1 << 20)
    return drv


@pytest.fixture
def image(tmpdir):
    path = tmpdir.join("image.bin")
    path.write(b"image")
    return str(path)


def writable(mocker, *results):
    """Make 'test -w' report each of the results in turn, then True"""
    codes = [0 if ok else 1 for ok in results]

    def run(cmd, check):
        assert cmd[:2] == ["test", "-w"]
        return subprocess.CompletedProcess(cmd, codes.pop(0) if codes else 0)

    return mocker.patch("labgrid.driver.usbstoragedriver.subprocess.run", side_effect=run)


def test_write_image_dd(storage, image, mocker):
    writable(mocker)
    pwrap = mocker.patch("labgrid.driver.usbstoragedriver.processwrapper")
    storage.write_image(image)
    args = pwrap.check_wrapped_output.call_args[0][1]
    assert args == [
        "dd",
        f"if={image}",
        "of=/dev/sdx",
        "oflag=direct",
        "status=progress",
        "bs=4M",
        "skip=0",
        "seek=0",
        "conv=fdatasync",
    ]


def test_wait_until_writable(storage, image, mocker):
    """The image is not written until udev has made the device writable"""
    run = writable(mocker, False, False, True)
    pwrap = mocker.patch("labgrid.driver.usbstoragedriver.processwrapper")
    storage.write_image(image)
    assert run.call_count == 3
    pwrap.check_wrapped_output.assert_called_once()


def test_not_writable(storage, image, mocker):
    """A device which never becomes writable gives a clear error"""
    writable(mocker, *[False] * 1000)
    pwrap = mocker.patch("labgrid.driver.usbstoragedriver.processwrapper")
    with pytest.raises(ExecutionError, match="/dev/sdx to be writable"):
        storage.write_image(image)
    pwrap.check_wrapped_output.assert_not_called()


@pytest.mark.parametrize(
    "kwargs,block_size",
    [
        ({}, "4M"),
        ({"seek": 16}, "512"),
        ({"seek": 8, "block_size": 1024}, "1024"),
        ({"block_size": "128K"}, "128K"),
    ],
)
def test_write_image_block_size(storage, image, mocker, kwargs, block_size):
    """The block size can be given, otherwise it depends on skip and seek"""
    writable(mocker)
    pwrap = mocker.patch("labgrid.driver.usbstoragedriver.processwrapper")
    storage.write_image(image, **kwargs)
    args = pwrap.check_wrapped_output.call_args[0][1]
    assert f"bs={block_size}" in args
    assert f"seek={kwargs.get('seek', 0)}" in args


def test_bmaptool_block_size(storage, image, mocker):
    writable(mocker)
    for kwargs in ({"block_size": 512}, {"count": 4}):
        with pytest.raises(ExecutionError, match="bmaptool does not support block_size or count"):
            storage.write_image(image, mode=Mode.BMAPTOOL, **kwargs)


def test_write_image_count(storage, image, mocker):
    """The number of blocks to write can be limited"""
    writable(mocker)
    pwrap = mocker.patch("labgrid.driver.usbstoragedriver.processwrapper")
    storage.write_image(image)
    assert not any(arg.startswith("count=") for arg in pwrap.check_wrapped_output.call_args[0][1])

    storage.write_image(image, seek=1, block_size="128K", count=3)
    args = pwrap.check_wrapped_output.call_args[0][1]
    assert args[-1] == "count=3"
    assert "bs=128K" in args
