import pytest

from labgrid.driver import LinkPiSmartHUBPowerDriver
from labgrid.protocol import PowerProtocol, ResetProtocol
from labgrid.resource import LinkPiSmartHUBPowerPort
from labgrid.resource.remote import NetworkLinkPiSmartHUBPowerPort
from labgrid.util.agents.linkpismarthub import methods, name_to_index
from labgrid.util.agentwrapper import AgentWrapper


@pytest.fixture(scope='function')
def local_smarthub_port(target):
    port = LinkPiSmartHUBPowerPort(target, name=None, index=1)
    port.avail = True
    yield port


@pytest.fixture(scope='function')
def remote_smarthub_port(target):
    yield NetworkLinkPiSmartHUBPowerPort(target,
        name=None,
        host="localhost",
        busnum=0,
        devnum=1,
        path='/dev/ttyUSB0',
        vendor_id=0x0,
        model_id=0x0,
        index=1,
    )


@pytest.fixture(scope='function')
def smarthub_driver(target, mocker):
    load_mock = mocker.patch.object(AgentWrapper, 'load')
    driver = LinkPiSmartHUBPowerDriver(target, name=None)
    target.activate(driver)
    yield driver, load_mock.return_value
    target.deactivate(driver)
    load_mock.reset_mock()


class TestLinkPiSmartHUBPowerDriver:
    def test_instanziation_local(self, target, local_smarthub_port):
        driver = LinkPiSmartHUBPowerDriver(target, name=None)
        assert (isinstance(driver, LinkPiSmartHUBPowerDriver))
        assert (isinstance(driver, PowerProtocol))
        assert (isinstance(driver, ResetProtocol))

    def test_instanziation_remote(self, target, remote_smarthub_port):
        driver = LinkPiSmartHUBPowerDriver(target, name=None)
        assert (isinstance(driver, LinkPiSmartHUBPowerDriver))
        assert (isinstance(driver, PowerProtocol))
        assert (isinstance(driver, ResetProtocol))

    def test_get(self, local_smarthub_port, smarthub_driver):
        driver, proxy_mock = smarthub_driver
        proxy_mock.get.return_value = True
        state = driver.get()
        assert state is True
        proxy_mock.get.assert_called_once_with(local_smarthub_port.path, local_smarthub_port.index)

    def test_on(self, local_smarthub_port, smarthub_driver):
        driver, proxy_mock = smarthub_driver
        driver.on()
        proxy_mock.set.assert_called_once_with(local_smarthub_port.path, local_smarthub_port.index, 1)

    def test_off(self, local_smarthub_port, smarthub_driver):
        driver, proxy_mock = smarthub_driver
        driver.off()
        proxy_mock.set.assert_called_once_with(local_smarthub_port.path, local_smarthub_port.index, 0)

    def test_cycle(self, mocker, local_smarthub_port, smarthub_driver):
        sleep_mock = mocker.patch("time.sleep")
        driver, proxy_mock = smarthub_driver
        driver.cycle()
        proxy_mock.set.assert_has_calls([
            mocker.call(local_smarthub_port.path, local_smarthub_port.index, 0),
            mocker.call(local_smarthub_port.path, local_smarthub_port.index, 1),
        ])
        sleep_mock.assert_called_once_with(driver.delay)


def test_linkpismarthub_name_to_index():
    for i in range(1, 7):
        assert name_to_index(str(i)) == 6 - i
        assert name_to_index(i) == i
    for i in range(7, 13):
        assert name_to_index(str(i)) == 12 + 6 - i
        assert name_to_index(i) == i


@pytest.mark.parametrize("path", ['', None])
def test_linkpismarthub_fail_missing_path(path):
    with pytest.raises(ValueError):
        methods["set"](path, 0, 1)
    with pytest.raises(ValueError):
        methods["get"](path, 0)


@pytest.mark.parametrize("path", ["/dev/ttyUSB0", "/dev/ttyUSB1"])
def test_linkpismarthub_use_correct_path(mocker, path):
    serial_mock = mocker.patch("serial.Serial")
    methods["set"](path, 0, 1)
    serial_mock.assert_called_once_with(path, 115200, timeout=mocker.ANY)
    serial_mock.reset_mock()
    s = serial_mock.return_value.__enter__()
    s.readline.return_value = b'{"Cmd":"StateResp","SeqNum":1,"state":[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]}\r\n'
    methods["get"](path, 0)
    serial_mock.assert_called_once_with(path, 115200, timeout=mocker.ANY)


def test_linkpismarthub_set(mocker):
    serial_mock = mocker.patch("serial.Serial")
    s = serial_mock.return_value.__enter__()
    methods["set"]("/dev/ttyUSB0", '1', 0)
    s.write.assert_called_once_with(b'onoff 5 0\r\n')
    serial_mock.reset_mock()
    methods["set"]("/dev/ttyUSB0", 5, 1)
    s.write.assert_called_once_with(b'onoff 5 1\r\n')


def test_linkpismarthub_get(mocker):
    serial_mock = mocker.patch("serial.Serial")
    s = serial_mock.return_value.__enter__()
    s.readline.side_effect = [
        b'{"Cmd":"VerResp","ver":"SmartHUB_1.0","uid":"1234"}\r\n',
        b'{"Cmd":"StateResp","SeqNum":1,"state":[0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0]}\r\n',
        b'{"Cmd":"VerResp","ver":"SmartHUB_1.0","uid":"1234"}\r\n',
        b'{"Cmd":"StateResp","SeqNum":2,"state":[0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0]}\r\n',
        b'{"Cmd":"VerResp","ver":"SmartHUB_1.0","uid":"1234"}\r\n',
        b'{"Cmd":"StateResp","SeqNum":3,"state":[0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]}\r\n',
    ]
    state = methods["get"]("/dev/ttyUSB0", '1')
    assert state == True
    s.write.assert_called_once_with(b'state\r\n')
    serial_mock.reset_mock()
    state = methods["get"]("/dev/ttyUSB0", 5)
    assert state == True
    s.write.assert_called_once_with(b'state\r\n')
    serial_mock.reset_mock()
    state = methods["get"]("/dev/ttyUSB0", 0)
    assert state == False
    s.write.assert_called_once_with(b'state\r\n')
