from unittest.mock import MagicMock, patch
import sys

import pytest

# mock laam before importing drivers
laam_mock = MagicMock()
laam_mock.exceptions.LAAError = type('LAAError', (Exception,), {})
sys.modules['laam'] = laam_mock
sys.modules['laam.exceptions'] = laam_mock.exceptions

from labgrid.resource.laa import (
    LAASerialPort, LAAPowerPort, LAAUSBGadgetMassStorage, LAAUSBPort,
    LAAButtonPort, LAALed, LAATempSensor, LAAWattMeter, LAAProvider,
)
from labgrid.driver.laadriver import (
    _get_laam,
    LAASerialDriver, LAAPowerDriver, LAAUSBGadgetMassStorageDriver,
    LAAUSBDriver, LAAButtonDriver, LAALedDriver, LAATempDriver,
    LAAWattDriver, LAAProviderDriver,
)
from labgrid.driver.exception import ExecutionError


class TestLAAResources:
    def test_serial_port(self, target):
        r = LAASerialPort(target, 'serial', laa_identity='test-laa', serial_name='ttymxc3')
        assert r.laa_identity == 'test-laa'
        assert r.serial_name == 'ttymxc3'

    def test_power_port(self, target):
        r = LAAPowerPort(
            target, 'power',
            laa_identity='test-laa',
            power_on=[('5v', 'on')],
            power_off=[('5v', 'off')],
        )
        assert r.power_on == [('5v', 'on')]
        assert r.power_cycle is None

    def test_usb_port(self, target):
        r = LAAUSBPort(target, 'usb', laa_identity='test-laa', usb_ports=[1, 2])
        assert r.usb_ports == [1, 2]

    def test_button_port(self, target):
        r = LAAButtonPort(target, 'button', laa_identity='test-laa', buttons=['power', 'reset'])
        assert r.buttons == ['power', 'reset']

    def test_led(self, target):
        r = LAALed(target, 'led', laa_identity='test-laa')
        assert r.laa_identity == 'test-laa'

    def test_temp_sensor(self, target):
        r = LAATempSensor(target, 'temp', laa_identity='test-laa')
        assert r.laa_identity == 'test-laa'

    def test_watt_meter(self, target):
        r = LAAWattMeter(target, 'watt', laa_identity='test-laa')
        assert r.laa_identity == 'test-laa'

    def test_power_port_bad_sequence(self, target):
        with pytest.raises(ValueError, match="must be .vbus, state."):
            LAAPowerPort(
                target, 'power',
                laa_identity='test-laa',
                power_on=[('5v',)],
                power_off=[('5v', 'off')],
            )

    def test_power_port_bad_entry_type(self, target):
        with pytest.raises(ValueError, match="must be .str, str."):
            LAAPowerPort(
                target, 'power',
                laa_identity='test-laa',
                power_on=[(5, 'on')],
                power_off=[('5v', 'off')],
            )


class TestGetLaam:
    def test_missing_laam(self):
        with patch('labgrid.driver.laadriver.import_module',
                   side_effect=ModuleNotFoundError("No module named 'laam'")):
            with pytest.raises(ModuleNotFoundError, match="install labgrid"):
                _get_laam()


class TestLAASerialDriver:
    def test_create(self, target):
        LAASerialPort(target, 'serial', laa_identity='test-laa', serial_name='ttymxc3')
        d = LAASerialDriver(target, 'driver')
        assert isinstance(d, LAASerialDriver)

    def test_activate_deactivate(self, target):
        LAASerialPort(target, 'serial', laa_identity='test-laa', serial_name='ttymxc3')
        d = LAASerialDriver(target, 'driver')
        target.activate(d)

        laam_mock.LAA.assert_called_with('test-laa')
        laam_mock.LAA().serials.connect_pexpect.assert_called_with('ttymxc3')

        target.deactivate(d)
        assert d._laa is None
        assert d._conn is None

    def test_read_encodes_str_to_bytes(self, target):
        LAASerialPort(target, 'serial', laa_identity='test-laa', serial_name='ttymxc3')
        d = LAASerialDriver(target, 'driver')
        target.activate(d)

        # ConnectPexpect returns str, driver must encode to bytes
        d._conn.read_nonblocking.return_value = "hello"
        result = d._read(size=5, timeout=1.0)
        assert result == b"hello"
        assert isinstance(result, bytes)

    def test_write(self, target):
        LAASerialPort(target, 'serial', laa_identity='test-laa', serial_name='ttymxc3')
        d = LAASerialDriver(target, 'driver')
        target.activate(d)

        d._write(b"test")
        d._conn.send.assert_called_with(b"test")


class TestLAAPowerDriver:
    def test_create(self, target):
        LAAPowerPort(
            target, 'power',
            laa_identity='test-laa',
            power_on=[('5v', 'on')],
            power_off=[('5v', 'off')],
        )
        d = LAAPowerDriver(target, 'driver')
        assert isinstance(d, LAAPowerDriver)

    def test_deactivate(self, target):
        LAAPowerPort(
            target, 'power',
            laa_identity='test-laa',
            power_on=[('5v', 'on')],
            power_off=[('5v', 'off')],
        )
        d = LAAPowerDriver(target, 'driver')
        target.activate(d)
        target.deactivate(d)
        assert d._laa is None

    def test_on_off(self, target):
        LAAPowerPort(
            target, 'power',
            laa_identity='test-laa',
            power_on=[('5v', 'on'), ('3v3', 'on')],
            power_off=[('3v3', 'off'), ('5v', 'off')],
        )
        d = LAAPowerDriver(target, 'driver')
        target.activate(d)

        d.on()
        calls = d._laa.laacli.power.call_args_list
        assert calls[-2][0] == ('5v', 'on')
        assert calls[-1][0] == ('3v3', 'on')

        d._laa.laacli.power.reset_mock()
        d.off()
        calls = d._laa.laacli.power.call_args_list
        assert calls[0][0] == ('3v3', 'off')
        assert calls[1][0] == ('5v', 'off')

    def test_cycle_default(self, target, mocker):
        mocker.patch('time.sleep')
        LAAPowerPort(
            target, 'power',
            laa_identity='test-laa',
            power_on=[('5v', 'on')],
            power_off=[('5v', 'off')],
        )
        d = LAAPowerDriver(target, 'driver')
        target.activate(d)
        d.cycle()

    def test_cycle_explicit(self, target):
        LAAPowerPort(
            target, 'power',
            laa_identity='test-laa',
            power_on=[('5v', 'on')],
            power_off=[('5v', 'off')],
            power_cycle=[('5v', 'reset')],
        )
        d = LAAPowerDriver(target, 'driver')
        target.activate(d)
        d.cycle()
        d._laa.laacli.power.assert_called_with('5v', 'reset')

    def test_power_error(self, target):
        LAAPowerPort(
            target, 'power',
            laa_identity='test-laa',
            power_on=[('5v', 'on')],
            power_off=[('5v', 'off')],
        )
        d = LAAPowerDriver(target, 'driver')
        target.activate(d)

        d._laa.laacli.power.side_effect = laam_mock.exceptions.LAAError("fail")
        with pytest.raises(ExecutionError):
            d.on()


class TestLAAUSBGadgetMassStorageDriver:
    def test_create(self, target):
        LAAUSBGadgetMassStorage(
            target, 'usbg_ms', laa_identity='test-laa', image='boot.img',
        )
        d = LAAUSBGadgetMassStorageDriver(target, 'driver')
        assert isinstance(d, LAAUSBGadgetMassStorageDriver)

    def test_deactivate(self, target):
        LAAUSBGadgetMassStorage(
            target, 'usbg_ms', laa_identity='test-laa', image='boot.img',
        )
        d = LAAUSBGadgetMassStorageDriver(target, 'driver')
        target.activate(d)
        target.deactivate(d)
        assert d._laa is None

    def test_on(self, target):
        LAAUSBGadgetMassStorage(
            target, 'usbg_ms', laa_identity='test-laa', image='boot.img',
        )
        d = LAAUSBGadgetMassStorageDriver(target, 'driver')
        target.activate(d)

        d.on()
        d._laa.laacli.usbg_ms.assert_called_with('on', 'boot.img')

    def test_off(self, target):
        LAAUSBGadgetMassStorage(
            target, 'usbg_ms', laa_identity='test-laa', image='boot.img',
        )
        d = LAAUSBGadgetMassStorageDriver(target, 'driver')
        target.activate(d)

        d.off()
        d._laa.laacli.usbg_ms.assert_called_with('off', '')

    def test_on_error(self, target):
        LAAUSBGadgetMassStorage(
            target, 'usbg_ms', laa_identity='test-laa', image='boot.img',
        )
        d = LAAUSBGadgetMassStorageDriver(target, 'driver')
        target.activate(d)

        d._laa.laacli.usbg_ms.side_effect = laam_mock.exceptions.LAAError("fail")
        with pytest.raises(ExecutionError):
            d.on()

    def test_off_error(self, target):
        LAAUSBGadgetMassStorage(
            target, 'usbg_ms', laa_identity='test-laa', image='boot.img',
        )
        d = LAAUSBGadgetMassStorageDriver(target, 'driver')
        target.activate(d)

        d._laa.laacli.usbg_ms.side_effect = laam_mock.exceptions.LAAError("fail")
        with pytest.raises(ExecutionError):
            d.off()


class TestLAAUSBDriver:
    def test_deactivate(self, target):
        LAAUSBPort(target, 'usb', laa_identity='test-laa', usb_ports=[1])
        d = LAAUSBDriver(target, 'driver')
        target.activate(d)
        target.deactivate(d)
        assert d._laa is None

    def test_on_off(self, target):
        LAAUSBPort(target, 'usb', laa_identity='test-laa', usb_ports=[1, 2])
        d = LAAUSBDriver(target, 'driver')
        target.activate(d)

        d.on()
        calls = d._laa.laacli.usb.call_args_list
        assert calls[-2][0] == (1, 'on')
        assert calls[-1][0] == (2, 'on')

        d._laa.laacli.usb.reset_mock()
        d.off()
        calls = d._laa.laacli.usb.call_args_list
        assert calls[0][0] == (1, 'off')
        assert calls[1][0] == (2, 'off')

    def test_off_error(self, target):
        LAAUSBPort(target, 'usb', laa_identity='test-laa', usb_ports=[1])
        d = LAAUSBDriver(target, 'driver')
        target.activate(d)

        d._laa.laacli.usb.side_effect = laam_mock.exceptions.LAAError("fail")
        with pytest.raises(ExecutionError):
            d.off()

    def test_on_error(self, target):
        LAAUSBPort(target, 'usb', laa_identity='test-laa', usb_ports=[1])
        d = LAAUSBDriver(target, 'driver')
        target.activate(d)

        d._laa.laacli.usb.side_effect = laam_mock.exceptions.LAAError("fail")
        with pytest.raises(ExecutionError):
            d.on()


class TestLAAButtonDriver:
    def test_deactivate(self, target):
        LAAButtonPort(target, 'button', laa_identity='test-laa', buttons=['power'])
        d = LAAButtonDriver(target, 'driver')
        target.activate(d)
        target.deactivate(d)
        assert d._laa is None

    def test_press_release(self, target):
        LAAButtonPort(target, 'button', laa_identity='test-laa', buttons=['power', 'reset'])
        d = LAAButtonDriver(target, 'driver')
        target.activate(d)

        d.press('power')
        d._laa.laacli.button.assert_called_with('power', 'on')

        d.release('power')
        d._laa.laacli.button.assert_called_with('power', 'off')

    def test_invalid_button(self, target):
        LAAButtonPort(target, 'button', laa_identity='test-laa', buttons=['power'])
        d = LAAButtonDriver(target, 'driver')
        target.activate(d)

        with pytest.raises(ExecutionError):
            d.press('nonexistent')

    def test_invalid_button_release(self, target):
        LAAButtonPort(target, 'button', laa_identity='test-laa', buttons=['power'])
        d = LAAButtonDriver(target, 'driver')
        target.activate(d)

        with pytest.raises(ExecutionError):
            d.release('nonexistent')

    def test_press_error(self, target):
        LAAButtonPort(target, 'button', laa_identity='test-laa', buttons=['power'])
        d = LAAButtonDriver(target, 'driver')
        target.activate(d)

        d._laa.laacli.button.side_effect = laam_mock.exceptions.LAAError("fail")
        with pytest.raises(ExecutionError):
            d.press('power')

    def test_release_error(self, target):
        LAAButtonPort(target, 'button', laa_identity='test-laa', buttons=['power'])
        d = LAAButtonDriver(target, 'driver')
        target.activate(d)

        d._laa.laacli.button.side_effect = laam_mock.exceptions.LAAError("fail")
        with pytest.raises(ExecutionError):
            d.release('power')


class TestLAALedDriver:
    def test_deactivate(self, target):
        LAALed(target, 'led', laa_identity='test-laa')
        d = LAALedDriver(target, 'driver')
        target.activate(d)
        target.deactivate(d)
        assert d._laa is None

    def test_on_off(self, target):
        LAALed(target, 'led', laa_identity='test-laa')
        d = LAALedDriver(target, 'driver')
        target.activate(d)

        d.on()
        d._laa.laacli.led.assert_called_with('on')

        d.off()
        d._laa.laacli.led.assert_called_with('off')

    def test_error(self, target):
        LAALed(target, 'led', laa_identity='test-laa')
        d = LAALedDriver(target, 'driver')
        target.activate(d)

        d._laa.laacli.led.side_effect = laam_mock.exceptions.LAAError("fail")
        with pytest.raises(ExecutionError):
            d.on()

    def test_off_error(self, target):
        LAALed(target, 'led', laa_identity='test-laa')
        d = LAALedDriver(target, 'driver')
        target.activate(d)

        d._laa.laacli.led.side_effect = laam_mock.exceptions.LAAError("fail")
        with pytest.raises(ExecutionError):
            d.off()


class TestLAATempDriver:
    def test_deactivate(self, target):
        LAATempSensor(target, 'temp', laa_identity='test-laa')
        d = LAATempDriver(target, 'driver')
        target.activate(d)
        target.deactivate(d)
        assert d._laa is None

    def test_get_temp(self, target):
        LAATempSensor(target, 'temp', laa_identity='test-laa')
        d = LAATempDriver(target, 'driver')
        target.activate(d)

        d._laa.laacli.temp.return_value = {'temp': 42.5}
        result = d.get_temp('dut')
        d._laa.laacli.temp.assert_called_with('dut')
        assert result == {'temp': 42.5}

    def test_error(self, target):
        LAATempSensor(target, 'temp', laa_identity='test-laa')
        d = LAATempDriver(target, 'driver')
        target.activate(d)

        d._laa.laacli.temp.side_effect = laam_mock.exceptions.LAAError("fail")
        with pytest.raises(ExecutionError):
            d.get_temp('dut')


class TestLAAWattDriver:
    def test_deactivate(self, target):
        LAAWattMeter(target, 'watt', laa_identity='test-laa')
        d = LAAWattDriver(target, 'driver')
        target.activate(d)
        target.deactivate(d)
        assert d._laa is None

    def test_get_watts(self, target):
        LAAWattMeter(target, 'watt', laa_identity='test-laa')
        d = LAAWattDriver(target, 'driver')
        target.activate(d)

        d._laa.laacli.watt.return_value = {'power': 2.5}
        result = d.get_watts('5v')
        d._laa.laacli.watt.assert_called_with('5v')
        assert result == {'power': 2.5}

    def test_error(self, target):
        LAAWattMeter(target, 'watt', laa_identity='test-laa')
        d = LAAWattDriver(target, 'driver')
        target.activate(d)

        d._laa.laacli.watt.side_effect = laam_mock.exceptions.LAAError("fail")
        with pytest.raises(ExecutionError):
            d.get_watts('5v')


class TestLAAProviderDriver:
    def test_deactivate(self, target):
        LAAProvider(target, 'provider', laa_identity='test-laa')
        d = LAAProviderDriver(target, 'driver')
        target.activate(d)
        target.deactivate(d)
        assert d._laa is None

    def test_create(self, target):
        LAAProvider(target, 'provider', laa_identity='test-laa')
        d = LAAProviderDriver(target, 'driver')
        assert isinstance(d, LAAProviderDriver)

    def test_stage_local(self, target, tmp_path):
        LAAProvider(target, 'provider', laa_identity='test-laa')
        d = LAAProviderDriver(target, 'driver')
        target.activate(d)

        test_file = tmp_path / "kernel.img"
        test_file.write_text("data")

        result = d.stage(str(test_file))
        d._laa.files.push.assert_called_with('kernel.img', str(test_file))
        assert result == 'kernel.img'

    def test_stage_url(self, target, mocker):
        import io

        LAAProvider(target, 'provider', laa_identity='test-laa')
        d = LAAProviderDriver(target, 'driver')
        target.activate(d)

        mock_response = MagicMock(wraps=io.BytesIO(b"data"))
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mocker.patch('labgrid.driver.laadriver.urlopen', return_value=mock_response)

        d._laa.files.push.reset_mock()
        result = d.stage('https://example.com/images/kernel.img')
        assert result == 'kernel.img'
        d._laa.files.push.assert_called_once()
        name, path = d._laa.files.push.call_args[0]
        assert name == 'kernel.img'

    def test_stage_missing_file(self, target):
        LAAProvider(target, 'provider', laa_identity='test-laa')
        d = LAAProviderDriver(target, 'driver')
        target.activate(d)

        with pytest.raises(ExecutionError, match="not found"):
            d.stage('/nonexistent/file.img')

    def test_list(self, target):
        LAAProvider(target, 'provider', laa_identity='test-laa')
        d = LAAProviderDriver(target, 'driver')
        target.activate(d)

        d._laa.files.list.return_value = ['kernel.img', 'dtb.dtb']
        result = d.list()
        d._laa.files.list.assert_called_once()
        assert result == ['kernel.img', 'dtb.dtb']

    def test_remove(self, target):
        LAAProvider(target, 'provider', laa_identity='test-laa')
        d = LAAProviderDriver(target, 'driver')
        target.activate(d)

        d.remove('kernel.img')
        d._laa.files.remove.assert_called_with('kernel.img')

    def test_remove_error(self, target):
        LAAProvider(target, 'provider', laa_identity='test-laa')
        d = LAAProviderDriver(target, 'driver')
        target.activate(d)

        d._laa.files.remove.side_effect = laam_mock.exceptions.LAAError("fail")
        with pytest.raises(ExecutionError):
            d.remove('kernel.img')
