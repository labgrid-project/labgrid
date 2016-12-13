import pytest

from labgrid.driver import NoResourceError
from labgrid.driver.powerdriver import ManualPowerDriver, ExternalPowerDriver

class TestManualPowerDriver:
    def test_create(self):
        d = ManualPowerDriver('foo-board')
        assert(isinstance(d, ManualPowerDriver))

    def test_on(self, mocker):
        m = mocker.patch('builtins.input')

        d = ManualPowerDriver('foo-board')
        d.on()

        m.assert_called_once_with("Turn the target foo-board ON and press enter")

    def test_off(self, mocker):
        m = mocker.patch('builtins.input')

        d = ManualPowerDriver('foo-board')
        d.off()

        m.assert_called_once_with("Turn the target foo-board OFF and press enter")

    def test_cycle(self, mocker):
        m = mocker.patch('builtins.input')

        d = ManualPowerDriver('foo-board')
        d.cycle()

        m.assert_called_once_with("CYCLE the target foo-board and press enter")

class TestExternalPowerDriver:
    def test_create(self):
        d = ExternalPowerDriver('foo-board', cmd_on='set -1 {name}', cmd_off='set -0 {name}')
        assert(isinstance(d, ExternalPowerDriver))

    def test_create_validator(self):
        with pytest.raises(ValueError):
            d = ExternalPowerDriver('foo-board', cmd_on='set -1', cmd_off='set -0')

    def test_on(self, mocker):
        m = mocker.patch('subprocess.check_call')

        d = ExternalPowerDriver('foo-board', cmd_on='set -1 {name}', cmd_off='set -0 {name}')
        d.on()

        m.assert_called_once_with('set -1 foo-board')

    def test_off(self, mocker):
        m = mocker.patch('subprocess.check_call')

        d = ExternalPowerDriver('foo-board', cmd_on='set -1 {name}', cmd_off='set -0 {name}')
        d.off()

        m.assert_called_once_with('set -0 foo-board')

    def test_cycle(self, mocker):
        m_sleep = mocker.patch('time.sleep')
        m = mocker.patch('subprocess.check_call')

        d = ExternalPowerDriver('foo-board', cmd_on='set -1 {name}', cmd_off='set -0 {name}')
        d.cycle()

        assert m.call_args_list == [
            mocker.call('set -0 foo-board'),
            mocker.call('set -1 foo-board'),
        ]
        m_sleep.assert_called_once_with(1.0)

    def test_cycle_explicit(self, mocker):
        m_sleep = mocker.patch('time.sleep')
        m = mocker.patch('subprocess.check_call')

        d = ExternalPowerDriver('foo-board',
            cmd_on='set -1 {name}',
            cmd_off='set -0 {name}',
            cmd_cycle='set -c {name}',
        )
        d.cycle()

        m.assert_called_once_with('set -c foo-board')
        m_sleep.assert_not_called()
