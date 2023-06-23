import pytest

from labgrid import Target
from labgrid.driver import BareboxDriver
from labgrid.driver.fake import FakeConsoleDriver
from labgrid.protocol import CommandProtocol, LinuxBootProtocol
from labgrid.driver import ExecutionError


class TestBareboxDriver:
    def test_create(self):
        t = Target('dummy')
        cp = FakeConsoleDriver(t, "console")
        d = BareboxDriver(t, "barebox")
        assert (isinstance(d, BareboxDriver))
        assert (isinstance(d, CommandProtocol))
        assert (isinstance(d, LinuxBootProtocol))

    def test_barebox_run(self, target_with_fakeconsole, mocker):
        t = target_with_fakeconsole
        d = BareboxDriver(t, "barebox")
        d = t.get_driver(BareboxDriver, activate=False)
        # mock for d._run('echo $global.loglevel')
        d._run = mocker.MagicMock(return_value=(['7'], [], 0))
        t.activate(d)
        d._run = mocker.MagicMock(return_value=(['success'], [], 0))
        res = d.run_check("test")
        assert res == ['success']
        res = d.run("test")
        assert res == (['success'], [], 0)

    def test_barebox_run_error(self, target_with_fakeconsole, mocker):
        t = target_with_fakeconsole
        d = BareboxDriver(t, "barebox")
        d = t.get_driver(BareboxDriver, activate=False)
        # mock for d._run('echo $global.loglevel')
        d._run = mocker.MagicMock(return_value=(['7'], [], 0))
        t.activate(d)
        d._run = mocker.MagicMock(return_value=(['error'], [], 1))
        with pytest.raises(ExecutionError):
            res = d.run_check("test")
        res = d.run("test")
        assert res == (['error'], [], 1)
