from tempfile import NamedTemporaryFile
import pytest

from labgrid.driver import RKUSBMaskromDriver
from labgrid.protocol import BootstrapProtocol
from labgrid.resource import RKUSBLoader
from labgrid.resource.remote import NetworkRKUSBLoader
from labgrid.util.agents.rkusbmaskrom import crc16_ccitt_false, crc32_rkboot, methods, rc4_ksa, rc4_prga
from labgrid.util.agentwrapper import AgentWrapper


@pytest.fixture(scope='function')
def local_rkusbloader(target):
    port = RKUSBLoader(target, name=None)
    port.avail = True
    yield port


@pytest.fixture(scope='function')
def remote_rkusbloader(target):
    yield NetworkRKUSBLoader(target,
        name=None,
        host="localhost",
        busnum=0,
        devnum=1,
        path='/dev/bus/usb/002/003',
        vendor_id=0x0,
        model_id=0x0,
    )


@pytest.fixture(scope='function')
def rkusbmaskrom_driver(target, mocker):
    load_mock = mocker.patch.object(AgentWrapper, 'load')
    driver = RKUSBMaskromDriver(target, name=None)
    target.activate(driver)
    yield driver, load_mock.return_value
    target.deactivate(driver)
    load_mock.reset_mock()


@pytest.fixture(scope='function')
def tempfile(target):
    with NamedTemporaryFile() as f:
        yield f


class TestRKUSBMaskromDriver:
    def test_instanziation_local(self, target, local_rkusbloader):
        driver = RKUSBMaskromDriver(target, name=None)
        assert (isinstance(driver, RKUSBMaskromDriver))
        assert (isinstance(driver, BootstrapProtocol))

    def test_instanziation_remote(self, target, remote_rkusbloader):
        driver = RKUSBMaskromDriver(target, name=None)
        assert (isinstance(driver, RKUSBMaskromDriver))
        assert (isinstance(driver, BootstrapProtocol))

    @pytest.mark.parametrize("filename", ['', None])
    def test_load_no_images(self, local_rkusbloader, rkusbmaskrom_driver, filename):
        driver, _ = rkusbmaskrom_driver
        with pytest.raises(Exception, match="No images to load"):
            driver.load(filename)

    def test_load(self, local_rkusbloader, rkusbmaskrom_driver, tempfile):
        driver, proxy_mock = rkusbmaskrom_driver
        driver.load(tempfile.name)
        proxy_mock.load.assert_called_once_with(
            local_rkusbloader.busnum,
            local_rkusbloader.devnum,
            tempfile.name,
            delay=driver.delay,
        )


def test_crc16_ccitt_false():
    crc = crc16_ccitt_false("123456789".encode())
    assert crc == 0x29b1


def test_crc32_rkboot():
    crc = crc32_rkboot("123456789".encode())
    assert crc == 0x889a9615


def test_rc4_keystream():
    # from RFC 6229: Test Vectors for the Stream Cipher RC4
    key = list(bytes.fromhex("1ada31d5cf688221c109163908ebe51debb46227c6cc8b37641910833222772a"))
    keystream = rc4_prga(rc4_ksa(key))
    assert [next(keystream) for _ in range(16)] == list(bytes.fromhex("dd5bcb0018e922d494759d7c395d02d3"))
    assert [next(keystream) for _ in range(16)] == list(bytes.fromhex("c8446f8f77abf737685353eb89a1c9eb"))
    for _ in range(4048):
        next(keystream)
    assert [next(keystream) for _ in range(16)] == list(bytes.fromhex("d5a39e3dfcc50280bac4a6b5aa0dca7d"))
    assert [next(keystream) for _ in range(16)] == list(bytes.fromhex("370b1c1fe655916d97fd0d47ca1d72b8"))


def test_rkusbmaskrom_device_not_found(mocker, tempfile):
    find_mock = mocker.patch("usb.core.find")
    find_mock.return_value = None
    with pytest.raises(ValueError, match="Device not found"):
        methods["load"](0, 1, tempfile.name, delay=0.001)


def test_rkusbmaskrom_unsupported_vendor(mocker, tempfile):
    dev_mock = mocker.patch("usb.core.find").return_value
    dev_mock.idVendor = 0x1234
    with pytest.raises(ValueError, match="Unsupported device VID 1234"):
        methods["load"](0, 1, tempfile.name, delay=0.001)


def test_rkusbmaskrom_loader_mode(mocker, tempfile):
    dev_mock = mocker.patch("usb.core.find").return_value
    dev_mock.idVendor = 0x2207
    dev_mock.bcdUSB = 0x0001
    with pytest.raises(ValueError, match="Device in LOADER mode"):
        methods["load"](0, 1, tempfile.name, delay=0.001)


@pytest.mark.parametrize("pid", [0x110a, 0x110c, 0x330a, 0x350a])
def test_rkusbmaskrom_load(mocker, tempfile, pid):
    dev_mock = mocker.patch("usb.core.find").return_value
    dev_mock.idVendor = 0x2207
    dev_mock.idProduct = pid
    dev_mock.bcdUSB = 0x0000
    methods["load"](0, 1, tempfile.name, delay=0.001)
    dev_mock.ctrl_transfer.assert_called()
