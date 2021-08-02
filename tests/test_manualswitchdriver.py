import pytest

from labgrid.driver.manualswitchdriver import ManualSwitchDriver


class TestManualSwitchDriver:
    def test_create(self, target):
        d = ManualSwitchDriver(target, "foo-switch")
        assert isinstance(d, ManualSwitchDriver)

    def test_set_on(self, target, mocker):
        m = mocker.patch("builtins.input")

        d = ManualSwitchDriver(target, "foo-switch")
        target.activate(d)
        d.set(True)

        m.assert_called_once_with(
            "Set foo-switch for target Test to ON and press enter"
        )

    def test_set_off(self, target, mocker):
        m = mocker.patch("builtins.input")

        d = ManualSwitchDriver(target, "foo-switch")
        target.activate(d)
        d.set(False)

        m.assert_called_once_with(
            "Set foo-switch for target Test to OFF and press enter"
        )

    def test_get(self, target, mocker):
        m = mocker.patch("builtins.input")

        d = ManualSwitchDriver(target, "foo-switch")
        target.activate(d)

        d.set(True)
        assert d.get() is True

        d.set(False)
        assert d.get() is False
