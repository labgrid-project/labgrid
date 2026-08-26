from unittest.mock import Mock

import pytest

from labgrid import Target
from labgrid.binding import BindingError
from labgrid.driver.common import Driver, check_file
from labgrid.driver.exception import ExecutionError


def test_driver_requires_target() -> None:
    with pytest.raises(BindingError):
        Driver(None, None)


def test_driver_get_priority_returns_zero_for_unknown_protocol(target: Target) -> None:
    class Protocol:
        pass

    driver = Driver(target, None)

    assert driver.get_priority(Protocol) == 0


def test_driver_get_export_vars_returns_empty_dict(target: Target) -> None:
    driver = Driver(target, None)

    assert driver.get_export_vars() == {}


def test_check_file_uses_default_command_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    call = Mock(return_value=0)
    monkeypatch.setattr("labgrid.driver.common.subprocess.call", call)

    check_file("/tmp/file")

    call.assert_called_once_with(["test", "-r", "/tmp/file"])


def test_check_file_raises_execution_error(monkeypatch: pytest.MonkeyPatch) -> None:
    call = Mock(return_value=1)
    monkeypatch.setattr("labgrid.driver.common.subprocess.call", call)

    with pytest.raises(ExecutionError, match="File /tmp/file is not readable"):
        check_file("/tmp/file")
