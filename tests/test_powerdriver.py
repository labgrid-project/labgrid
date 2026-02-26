from urllib.parse import urlparse

import pytest

from labgrid.resource import NetworkPowerPort, YKUSHPowerPort
from labgrid.driver.powerdriver import (
    ExternalPowerDriver,
    ManualPowerDriver,
    NetworkPowerDriver,
    YKUSHPowerDriver,
)
from labgrid.util.helper import processwrapper


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
        import labgrid.driver.power.rest
        import labgrid.driver.power.sentry
        import labgrid.driver.power.sentry_sequential
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
        pytest.importorskip("vxi11")
        import labgrid.driver.power.siglent

    def test_import_backend_poe_mib(self):
        pytest.importorskip("pysnmp")
        import labgrid.driver.power.poe_mib


class TestSentrySequentialBackend:
    def test_power_get_on_value_3(self, mocker):
        from labgrid.driver.power import sentry_sequential

        mock_output = mocker.patch(
            'labgrid.driver.power.sentry_sequential.processwrapper.check_output'
        )
        mock_output.return_value = b'.1.3.6.1.4.1.1718.3.2.3.1.10.1.1.5 3'

        result = sentry_sequential.power_get('host', None, 5)
        assert result is True

    def test_power_get_on_value_5(self, mocker):
        from labgrid.driver.power import sentry_sequential

        mock_output = mocker.patch(
            'labgrid.driver.power.sentry_sequential.processwrapper.check_output'
        )
        mock_output.return_value = b'.1.3.6.1.4.1.1718.3.2.3.1.10.1.1.5 5'

        result = sentry_sequential.power_get('host', None, 5)
        assert result is True

    def test_power_get_off(self, mocker):
        from labgrid.driver.power import sentry_sequential

        mock_output = mocker.patch(
            'labgrid.driver.power.sentry_sequential.processwrapper.check_output'
        )
        mock_output.return_value = b'.1.3.6.1.4.1.1718.3.2.3.1.10.1.1.5 4'

        result = sentry_sequential.power_get('host', None, 5)
        assert result is False

    def test_power_set_on(self, mocker):
        from labgrid.driver.power import sentry_sequential

        mock_output = mocker.patch(
            'labgrid.driver.power.sentry_sequential.processwrapper.check_output'
        )

        sentry_sequential.power_set('host', None, 5, True)

        mock_output.assert_called_once()
        call_args = mock_output.call_args[0][0]
        assert 'int' in call_args
        assert '1' in call_args

    def test_power_set_off(self, mocker):
        from labgrid.driver.power import sentry_sequential

        mock_output = mocker.patch(
            'labgrid.driver.power.sentry_sequential.processwrapper.check_output'
        )

        sentry_sequential.power_set('host', None, 5, False)

        call_args = mock_output.call_args[0][0]
        assert 'int' in call_args
        assert '2' in call_args

    def test_power_set_index_bounds(self):
        from labgrid.driver.power import sentry_sequential

        with pytest.raises(AssertionError):
            sentry_sequential.power_set('host', None, 0, True)

        with pytest.raises(AssertionError):
            sentry_sequential.power_set('host', None, 17, True)

    def test_power_get_index_bounds(self):
        from labgrid.driver.power import sentry_sequential

        with pytest.raises(AssertionError):
            sentry_sequential.power_get('host', None, 0)

        with pytest.raises(AssertionError):
            sentry_sequential.power_get('host', None, 17)

    def test_power_set_port_must_be_none(self):
        from labgrid.driver.power import sentry_sequential

        with pytest.raises(AssertionError):
            sentry_sequential.power_set('host', 'port', 5, True)

    def test_power_get_port_must_be_none(self):
        from labgrid.driver.power import sentry_sequential

        with pytest.raises(AssertionError):
            sentry_sequential.power_get('host', 'port', 5)

    def test_power_set_error_handling(self, mocker):
        from labgrid.driver.power import sentry_sequential
        from labgrid.driver.exception import ExecutionError

        mock_output = mocker.patch(
            'labgrid.driver.power.sentry_sequential.processwrapper.check_output'
        )
        mock_output.side_effect = Exception("SNMP failed")

        with pytest.raises(ExecutionError):
            sentry_sequential.power_set('host', None, 5, True)

    def test_power_get_oid_mapping(self, mocker):
        from labgrid.driver.power import sentry_sequential

        mock_output = mocker.patch(
            'labgrid.driver.power.sentry_sequential.processwrapper.check_output'
        )
        mock_output.return_value = b'.1.3.6.1.4.1.1718.3.2.3.1.10.1.1.1 3'

        sentry_sequential.power_get('host', None, 1)

        call_args = mock_output.call_args[0][0]
        # Verify OID ends with .1.1.1 for index 1
        assert '.1.3.6.1.4.1.1718.3.2.3.1.10.1.1.1' in call_args

    def test_power_set_oid_mapping(self, mocker):
        from labgrid.driver.power import sentry_sequential

        mock_output = mocker.patch(
            'labgrid.driver.power.sentry_sequential.processwrapper.check_output'
        )

        sentry_sequential.power_set('host', None, 16, True)

        call_args = mock_output.call_args[0][0]
        # Verify OID ends with .1.1.16 for index 16
        assert '.1.3.6.1.4.1.1718.3.2.3.1.11.1.1.16' in call_args

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
