import pytest

from labgrid.driver import ShellDriver, ExecutionError
from labgrid.exceptions import NoDriverFoundError


class TestShellDriver:
    def test_instance(self, target, serial_driver):
        s = ShellDriver(target, "shell", "", "", "")
        assert (isinstance(s, ShellDriver))

    def test_no_driver(self, target):
        with pytest.raises(NoDriverFoundError):
            ShellDriver(target, "shell", "", "", "")

    def test_run(self, target_with_fakeconsole, mocker):
        t = target_with_fakeconsole
        d = ShellDriver(t, "shell", prompt='dummy', login_prompt='dummy', username='dummy')
        d.on_activate = mocker.MagicMock()
        d = t.get_driver('ShellDriver')
        d._run = mocker.MagicMock(return_value=(['success'], [], 0))
        res = d.run_check("test")
        assert res == ['success']
        res = d.run("test")
        assert res == (['success'], [], 0)

    def test_run_error(self, target_with_fakeconsole, mocker):
        t = target_with_fakeconsole
        d = ShellDriver(t, "shell", prompt='dummy', login_prompt='dummy', username='dummy')
        d.on_activate = mocker.MagicMock()
        d = t.get_driver('ShellDriver')
        d._run = mocker.MagicMock(return_value=(['error'], [], 1))
        with pytest.raises(ExecutionError):
            res = d.run_check("test")
        res = d.run("test")
        assert res == (['error'], [], 1)

    def test_run_with_timeout(self, target_with_fakeconsole, mocker):
        t = target_with_fakeconsole
        d = ShellDriver(t, "shell", prompt='dummy', login_prompt='dummy', username='dummy')
        d.on_activate = mocker.MagicMock()
        d = t.get_driver('ShellDriver')
        d._run = mocker.MagicMock(return_value=(['success'], [], 0))
        res = d.run_check("test", timeout=30.0)
        assert res == ['success']
        res = d.run("test")
        assert res == (['success'], [], 0)
