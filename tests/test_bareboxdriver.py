import pytest

from labgrid import Target
from labgrid.driver import BareboxDriver
from labgrid.driver.fake import FakeConsoleDriver
from labgrid.protocol import CommandProtocol, LinuxBootProtocol
from labgrid.driver import ExecutionError


def _get_active_barebox(target_with_fakeconsole, mocker):
    t = target_with_fakeconsole
    d = BareboxDriver(t, "barebox")
    d = t.get_driver(BareboxDriver, activate=False)
    # mock for d._run('echo $global.loglevel')
    d._run = mocker.MagicMock(return_value=(['7'], [], 0))
    t.activate(d)
    return d


class TestBareboxDriver:
    def test_create(self):
        t = Target('dummy')
        cp = FakeConsoleDriver(t, "console")
        d = BareboxDriver(t, "barebox")
        assert (isinstance(d, BareboxDriver))
        assert (isinstance(d, CommandProtocol))
        assert (isinstance(d, LinuxBootProtocol))

    def test_barebox_run(self, target_with_fakeconsole, mocker):
        d = _get_active_barebox(target_with_fakeconsole, mocker)
        d._run = mocker.MagicMock(return_value=(['success'], [], 0))
        res = d.run_check("test")
        assert res == ['success']
        res = d.run("test")
        assert res == (['success'], [], 0)

    def test_barebox_run_error(self, target_with_fakeconsole, mocker):
        d = _get_active_barebox(target_with_fakeconsole, mocker)
        d._run = mocker.MagicMock(return_value=(['error'], [], 1))
        with pytest.raises(ExecutionError):
            res = d.run_check("test")
        res = d.run("test")
        assert res == (['error'], [], 1)

    def test_barebox_reset(self, target_with_fakeconsole, mocker):
        d = _get_active_barebox(target_with_fakeconsole, mocker)

        d.boot_expression = "[\n]barebox 2345"
        d.prompt = prompt = ">="
        d._check_prompt = mocker.MagicMock()
        d.console.rxq.extend([prompt.encode(), b"\nbarebox 2345"])
        d.reset()

        assert d.console.txq.pop() == b"reset\n"
        assert d._status == 1
        assert d.boot_detected

        d.console.rxq.append(prompt.encode())
        with pytest.raises(ExecutionError):
            d.reset()

