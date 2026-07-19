from urllib.parse import urlparse

import pytest

from labgrid.driver import ExecutionError
from labgrid.driver.power.poe_netgear_plus import _get_hostname_and_password
from labgrid.resource import NetworkPowerPort, YKUSHPowerPort
from labgrid.driver.powerdriver import (
    ExternalPowerDriver,
    ManualPowerDriver,
    NetworkPowerDriver,
    YKUSHPowerDriver,
)


class TestManualPowerDriver:
    def test_create(self, target):
        d = ManualPowerDriver(target, 'foo-board')
        assert (isinstance(d, ManualPowerDriver))

    def test_on(self, target, mocker):
        m = mocker.patch('builtins.input')

        d = ManualPowerDriver(target, 'foo-board')
        target.activate(d)
        d.on()

        m.assert_called_once_with(
            "Turn the target Test ON and press enter"
        )

    def test_off(self, target, mocker):
        m = mocker.patch('builtins.input')

        d = ManualPowerDriver(target, 'foo-board')
        target.activate(d)
        d.off()

        m.assert_called_once_with(
            "Turn the target Test OFF and press enter"
        )

    def test_cycle(self, target, mocker):
        m = mocker.patch('builtins.input')

        d = ManualPowerDriver(target, 'foo-board')
        target.activate(d)
        d.cycle()

        m.assert_called_once_with("CYCLE the target Test and press enter")


class TestExternalPowerDriver:
    def test_create(self, target):
        d = ExternalPowerDriver(
            target, 'power', cmd_on='set -1 foo-board', cmd_off='set -0 foo-board'
        )
        assert (isinstance(d, ExternalPowerDriver))

    def test_on(self, target, mocker):
        pty = mocker.patch('pty.openpty')
        mocker.patch('fcntl.fcntl')
        fdopen = mocker.patch('os.fdopen')
        close = mocker.patch('os.close')
        popen = mocker.patch('subprocess.Popen')
        select = mocker.patch('select.select')
        fd_mock = mocker.MagicMock()
        instance_mock = mocker.MagicMock()
        select_mock = mocker.MagicMock()
        popen.return_value = instance_mock
        fdopen.return_value = fd_mock
        pty.return_value = (instance_mock, 2)
        fd_mock.read.return_value = b'Done\nDone'
        instance_mock.returncode = 0
        select.return_value = ([], [], [])

        d = ExternalPowerDriver(
            target, 'power', cmd_on='set -1 foo-board', cmd_off='set -0 foo-board'
        )
        target.activate(d)
        d.on()

        popen.assert_called_once_with(['set', '-1', 'foo-board'], bufsize=0,
                                      stderr=2, stdout=2)

    def test_off(self, target, mocker):
        pty = mocker.patch('pty.openpty')
        mocker.patch('fcntl.fcntl')
        fdopen = mocker.patch('os.fdopen')
        close = mocker.patch('os.close')
        popen = mocker.patch('subprocess.Popen')
        select = mocker.patch('select.select')
        fd_mock = mocker.MagicMock()
        instance_mock = mocker.MagicMock()
        select_mock = mocker.MagicMock()
        popen.return_value = instance_mock
        fdopen.return_value = fd_mock
        pty.return_value = (instance_mock, 2)
        fd_mock.read.return_value = b'Done\nDone'
        instance_mock.returncode = 0
        select.return_value = ([], [], [])

        d = ExternalPowerDriver(
            target, 'power', cmd_on='set -1 foo-board', cmd_off='set -0 foo-board'
        )
        target.activate(d)
        d.off()

        popen.assert_called_once_with(['set', '-0', 'foo-board'], bufsize=0,
                                      stderr=2, stdout=2)

    def test_cycle(self, target, mocker):
        pty = mocker.patch('pty.openpty')
        mocker.patch('fcntl.fcntl')
        fdopen = mocker.patch('os.fdopen')
        close = mocker.patch('os.close')
        popen = mocker.patch('subprocess.Popen')
        select = mocker.patch('select.select')
        fd_mock = mocker.MagicMock()
        instance_mock = mocker.MagicMock()
        select_mock = mocker.MagicMock()
        popen.return_value = instance_mock
        fdopen.return_value = fd_mock
        pty.return_value = (instance_mock, 2)
        fd_mock.read.return_value = b'Done\nDone'
        instance_mock.returncode = 0
        select.return_value = ([], [], [])

        m_sleep = mocker.patch('time.sleep')

        d = ExternalPowerDriver(
            target, 'power', cmd_on='set -1 foo-board', cmd_off='set -0 foo-board'
        )
        target.activate(d)
        d.cycle()

        assert popen.call_args_list == [
            mocker.call(['set', '-0', 'foo-board'], bufsize=0, stderr=2,
                        stdout=2),
            mocker.call(['set', '-1', 'foo-board'], bufsize=0, stderr=2,
                        stdout=2),
        ]
        m_sleep.assert_called_once_with(2.0)

    def test_cycle_explicit(self, target, mocker):
        pty = mocker.patch('pty.openpty')
        mocker.patch('fcntl.fcntl')
        fdopen = mocker.patch('os.fdopen')
        close = mocker.patch('os.close')
        popen = mocker.patch('subprocess.Popen')
        select = mocker.patch('select.select')
        fd_mock = mocker.MagicMock()
        instance_mock = mocker.MagicMock()
        select_mock = mocker.MagicMock()
        popen.return_value = instance_mock
        fdopen.return_value = fd_mock
        pty.return_value = (instance_mock, 2)
        fd_mock.read.return_value = b'Done\nDone'
        instance_mock.returncode = 0
        select.return_value = ([], [], [])

        m_sleep = mocker.patch('time.sleep')

        d = ExternalPowerDriver(
            target, 'power',
            cmd_on='set -1 foo-board',
            cmd_off='set -0 foo-board',
            cmd_cycle='set -c foo-board',
        )
        target.activate(d)
        d.cycle()

        popen.assert_called_once_with(['set', '-c', 'foo-board'], bufsize=0,
                                      stderr=2, stdout=2)
        m_sleep.assert_not_called()

class TestNetworkPowerDriver:
    def test_create(self, target):
        r = NetworkPowerPort(target, 'power', model='netio', host='dummy', index='1')
        d = NetworkPowerDriver(target, 'power')
        assert isinstance(d, NetworkPowerDriver)

    @pytest.mark.parametrize('backend', ('rest', 'simplerest'))
    @pytest.mark.parametrize(
        'host',
        (
            'http://example.com/{index}',
            'https://example.com/{index}',
            'http://example.com:1234/{index}',
            'https://example.com:1234/{index}',
            'http://user:pass@example.com:1234/{index}',
            'https://user:pass@example.com:1234/{index}',
        )
    )
    def test_create_backend_with_url_in_host(self, target, mocker, backend, host):
        get = mocker.patch('requests.get')
        get.return_value.text = '1'
        mocker.patch('requests.put')

        index = '1'
        NetworkPowerPort(target, 'power', model=backend, host=host, index=index)
        d = NetworkPowerDriver(target, 'power')
        assert isinstance(d, NetworkPowerDriver)
        target.activate(d)

        d.cycle()
        assert d.get() is True

        # the called URL should be similar to the one configured in the resource, but with
        # index and explicit port
        expected_host = host.format(index=index)
        url = urlparse(expected_host)
        if url.port is None:
            implicit_port = 443 if url.scheme == 'https' else 80
            expected_host = expected_host.replace(url.netloc, f'{url.netloc}:{implicit_port}')

        get.assert_called_with(expected_host)

    @pytest.mark.parametrize(
        'host',
        (
            'http://example.com',
            'https://example.com',
        )
    )
    def test_create_shelly_gen1_backend_with_url_in_host(self, target, mocker, host):
        get = mocker.patch('requests.get')
        get.return_value.text = '{"ison": true}'
        mocker.patch('requests.post')

        index = '0'
        NetworkPowerPort(target, 'power', model='shelly_gen1', host=host, index=index)
        d = NetworkPowerDriver(target, 'power')
        target.activate(d)

        d.cycle()
        assert d.get() is True

        # the called URL should be similar to the one configured in the resource, but with
        # index and explicit port
        expected_host = f"{host}/relay/{index}"
        url = urlparse(expected_host)
        if url.port is None:
            implicit_port = 443 if url.scheme == "https" else 80
            expected_host = expected_host.replace(
                url.netloc, f"{url.netloc}:{implicit_port}"
            )

        get.assert_called_with(expected_host)

    def test_create_ubus_backend(self, target, mocker):
        post = mocker.patch("requests.post")
        post.return_value.json.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": [
                0,
                {
                    "firmware": "v80.1",
                    "budget": 77.000000,
                    "consumption": 1.700000,
                    "ports": {
                        "lan1": {
                            "priority": 0,
                            "mode": "PoE+",
                            "status": "Delivering power",
                            "consumption": 1.700000,
                        }
                    },
                },
            ],
        }

        index = "1"
        NetworkPowerPort(
            target, "power", model="ubus", host="http://example.com/ubus", index=index
        )
        d = NetworkPowerDriver(target, "power")
        target.activate(d)

        d.cycle()
        assert d.get() is True

    def test_import_backends(self):
        import labgrid.driver.power
        import labgrid.driver.power.apc
        import labgrid.driver.power.digipower
        import labgrid.driver.power.digitalloggers_http
        import labgrid.driver.power.digitalloggers_restapi
        import labgrid.driver.power.eth008
        import labgrid.driver.power.gude
        import labgrid.driver.power.gude24
        import labgrid.driver.power.netio
        import labgrid.driver.power.netio_kshell
        import labgrid.driver.power.pe6216
        import labgrid.driver.power.poe_netgear_plus
        import labgrid.driver.power.rest
        import labgrid.driver.power.sentry
        import labgrid.driver.power.eg_pms2_network
        import labgrid.driver.power.shelly_gen1
        import labgrid.driver.power.ubus
        import labgrid.driver.power.tinycontrol_tcpdu

    def test_import_backend_eaton(self):
        pytest.importorskip("pysnmp")
        import labgrid.driver.power.eaton

    def test_import_backend_tplink(self):
        pytest.importorskip("kasa")
        import labgrid.driver.power.tplink

    def test_import_backend_siglent(self):
        pytest.importorskip("pyvisa")
        import labgrid.driver.power.siglent

    def test_import_backend_poe_mib(self):
        pytest.importorskip("pysnmp")
        import labgrid.driver.power.poe_mib

    def _mock_siglent_psu(self, mocker, responses=None):
        rm = mocker.patch("pyvisa.ResourceManager")
        psu = rm.return_value.open_resource.return_value
        # `with _get_psu(...) as psu` must yield the same mock we configure
        psu.__enter__.return_value = psu
        if responses is not None:
            psu.query.side_effect = lambda cmd: responses[cmd]
        return psu

    def _activate_siglent_driver(self, target):
        NetworkPowerPort(target, "power", model="siglent", host="192.0.2.1", index="1")
        d = NetworkPowerDriver(target, "power")
        target.activate(d)
        return d

    def test_siglent_on_off_get(self, target, mocker):
        pytest.importorskip("pyvisa")

        # CH1 output state is reported in bit 4 of the hex SYSTEM:STATUS? value
        psu = self._mock_siglent_psu(mocker, {"SYSTEM:STATUS?": "0x0010"})
        d = self._activate_siglent_driver(target)

        d.on()
        psu.write.assert_called_with("OUTPUT CH1,ON")
        d.off()
        psu.write.assert_called_with("OUTPUT CH1,OFF")

        assert d.get() is True
        psu.query.side_effect = lambda cmd: {"SYSTEM:STATUS?": "0x0000"}[cmd]
        assert d.get() is False

    def test_siglent_show(self, target, mocker):
        pytest.importorskip("pyvisa")

        self._mock_siglent_psu(mocker, {
            "MEAS:VOLT? CH1": "5.001",
            "MEAS:CURR? CH1": "0.209",
            "MEAS:POWE? CH1": "1.045",
            "CH1:VOLT?": "5.0",
            "CH1:CURR?": "1.5",
        })
        d = self._activate_siglent_driver(target)

        assert d.show() == {
            "voltage": 5.001,
            "amps": 0.209,
            "watts": 1.045,
            "v_limit": 5.0,
            "a_limit": 1.5,
        }

    def test_siglent_voltage_amps(self, target, mocker):
        pytest.importorskip("pyvisa")

        psu = self._mock_siglent_psu(mocker)
        d = self._activate_siglent_driver(target)

        d.voltage(5.0)
        psu.write.assert_called_with("CH1:VOLT 5.0")
        d.amps(1.5)
        psu.write.assert_called_with("CH1:CURR 1.5")

    def test_siglent_power_watts(self, mocker):
        pytest.importorskip("pyvisa")
        from labgrid.driver.power import siglent

        psu = self._mock_siglent_psu(mocker, {"MEAS:POWE? CH2": "2.5"})

        # power is read from the device, not derived from voltage * current
        assert siglent.power_watts("192.0.2.1", None, 2) == 2.5
        psu.query.assert_called_once_with("MEAS:POWE? CH2")

class TestYKUSHPowerDriver:
    YKUSH_FAKE_SERIAL = "YK12345"
    YKUSH_LIST_OUTPUT = f"Attached YKUSH Boards:\n1. Board found with serial number: {YKUSH_FAKE_SERIAL}".encode(
        "utf-8"
    )
    YKUSH3_FAKE_SERIAL = "Y3N10673"
    YKUSH3_LIST_OUTPUT = f"Attached YKUSH3 Boards:\n1. Board found with serial number: {YKUSH3_FAKE_SERIAL}".encode(
        "utf-8"
    )
    YKUSHXS_LIST_OUTPUT = (
        "Attached YKUSH XS Boards:\n1. Board found with serial number: YKU1234".encode(
            "utf-8"
        )
    )

    def test_create(self, target):
        resource = YKUSHPowerPort(
            target, "power", serial=self.YKUSH_FAKE_SERIAL, index=1
        )
        device = YKUSHPowerDriver(target, "power")
        assert isinstance(device, YKUSHPowerDriver)

    def test_default_off(self, target, mocker):
        check_output_mock = mocker.patch(
            "labgrid.util.helper.processwrapper.check_output"
        )
        check_output_mock.side_effect = [
            self.YKUSH_LIST_OUTPUT,
            self.YKUSHXS_LIST_OUTPUT,
            self.YKUSH3_LIST_OUTPUT,
            b"",
        ]
        resource = YKUSHPowerPort(
            target, "power", serial=self.YKUSH_FAKE_SERIAL, index=2
        )
        resource.avail = True
        device = YKUSHPowerDriver(target, "power")
        target.activate(device)
        device.off()

        check_output_mock.assert_called_with(
            ["ykushcmd", "ykush", "-s", self.YKUSH_FAKE_SERIAL, "-d", "2"]
        )

    def test_ykush3_on(self, target, mocker):
        check_output_mock = mocker.patch(
            "labgrid.util.helper.processwrapper.check_output"
        )
        check_output_mock.side_effect = [
            self.YKUSH_LIST_OUTPUT,
            self.YKUSHXS_LIST_OUTPUT,
            self.YKUSH3_LIST_OUTPUT,
            b"",
        ]
        resource = YKUSHPowerPort(
            target, "power", serial=self.YKUSH3_FAKE_SERIAL, index=3
        )
        resource.avail = True
        device = YKUSHPowerDriver(target, "power")
        target.activate(device)
        device.on()

        check_output_mock.assert_called_with(
            ["ykushcmd", "ykush3", "-s", self.YKUSH3_FAKE_SERIAL, "-u", "3"]
        )


class TestPoeNetgearPlusPowerDriver:
    @pytest.mark.parametrize(
        'url, expected_host, expected_pw',
        [
            ("http://example.com", "example.com", "P4ssword"),
            ("http://ignored:detected_pw@example.com", "example.com", "detected_pw"),
        ]
    )
    def test_get_hostname_and_password(self, url: str, expected_host: str, expected_pw: str):
        returned_host, returned_pw = _get_hostname_and_password(url)
        assert returned_host == expected_host
        assert returned_pw == expected_pw

    def test_get_hostname_and_pw_non_http_raises(self):
        with pytest.raises(ExecutionError, match="URL must start with http://"):
            _get_hostname_and_password("no_http_protocol")
