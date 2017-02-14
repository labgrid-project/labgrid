import pytest

from labgrid.driver.powerdriver import ExternalPowerDriver, ManualPowerDriver


class TestManualPowerDriver:
    def test_create(self, target):
        d = ManualPowerDriver(target, name='foo-board')
        assert (isinstance(d, ManualPowerDriver))

    def test_on(self, target, mocker):
        m = mocker.patch('builtins.input')

        d = ManualPowerDriver(target, name='foo-board')
        d.on()

        m.assert_called_once_with(
            "Turn the target foo-board ON and press enter"
        )

    def test_off(self, target, mocker):
        m = mocker.patch('builtins.input')

        d = ManualPowerDriver(target, name='foo-board')
        d.off()

        m.assert_called_once_with(
            "Turn the target foo-board OFF and press enter"
        )

    def test_cycle(self, target, mocker):
        m = mocker.patch('builtins.input')

        d = ManualPowerDriver(target, name='foo-board')
        d.cycle()

        m.assert_called_once_with("CYCLE the target foo-board and press enter")


class TestExternalPowerDriver:
    def test_create(self, target):
        d = ExternalPowerDriver(
            target, cmd_on='set -1 foo-board', cmd_off='set -0 foo-board'
        )
        assert (isinstance(d, ExternalPowerDriver))

    def test_on(self, target, mocker):
        m = mocker.patch('subprocess.check_call')

        d = ExternalPowerDriver(
            target, cmd_on='set -1 foo-board', cmd_off='set -0 foo-board'
        )
        d.on()

        m.assert_called_once_with('set -1 foo-board')

    def test_off(self, target, mocker):
        m = mocker.patch('subprocess.check_call')

        d = ExternalPowerDriver(
            target, cmd_on='set -1 foo-board', cmd_off='set -0 foo-board'
        )
        d.off()

        m.assert_called_once_with('set -0 foo-board')

    def test_cycle(self, target, mocker):
        m_sleep = mocker.patch('time.sleep')
        m = mocker.patch('subprocess.check_call')

        d = ExternalPowerDriver(
            target, cmd_on='set -1 foo-board', cmd_off='set -0 foo-board'
        )
        d.cycle()

        assert m.call_args_list == [
            mocker.call('set -0 foo-board'),
            mocker.call('set -1 foo-board'),
        ]
        m_sleep.assert_called_once_with(2.0)

    def test_cycle_explicit(self, target, mocker):
        m_sleep = mocker.patch('time.sleep')
        m = mocker.patch('subprocess.check_call')

        d = ExternalPowerDriver(
            target,
            cmd_on='set -1 foo-board',
            cmd_off='set -0 foo-board',
            cmd_cycle='set -c foo-board',
        )
        d.cycle()

        m.assert_called_once_with('set -c foo-board')
        m_sleep.assert_not_called()
