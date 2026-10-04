import asyncio
import errno
import random
import sys
from unittest.mock import Mock, call

import pytest

from labgrid.remote import exporter
from labgrid.util import helper, ssh


@pytest.fixture
def port_socket(monkeypatch):
    monkeypatch.setattr(helper, "_port_range", None, raising=False)
    monkeypatch.setattr(helper, "random", random, raising=False)
    sock = Mock()
    monkeypatch.setattr(helper, "socket", Mock(return_value=sock))
    return sock


def test_get_free_port_default(port_socket):
    port_socket.getsockname.return_value = ("", 32768)

    assert helper.get_free_port() == 32768

    port_socket.bind.assert_called_once_with(("", 0))
    port_socket.close.assert_called_once_with()


def test_get_free_port_range(monkeypatch, port_socket):
    monkeypatch.setattr(helper, "_port_range", range(4000, 4003))
    sample = Mock(return_value=[4001, 4002, 4000])
    monkeypatch.setattr(helper.random, "sample", sample)
    port_socket.bind.side_effect = [OSError(errno.EADDRINUSE, "occupied"), None]
    port_socket.getsockname.return_value = ("", 4002)

    assert helper.get_free_port() == 4002

    sample.assert_called_once_with(range(4000, 4003), 3)
    assert port_socket.bind.call_args_list == [call(("", 4000)), call(("", 4002))]
    port_socket.close.assert_called_once_with()


def test_get_free_port_range_exhausted(monkeypatch, port_socket):
    monkeypatch.setattr(helper, "_port_range", range(4000, 4002))
    monkeypatch.setattr(helper.random, "sample", lambda ports, count: list(ports))
    port_socket.bind.side_effect = OSError(errno.EADDRINUSE, "occupied")

    with pytest.raises(OSError) as excinfo:
        helper.get_free_port()

    assert excinfo.value.errno == errno.EADDRINUSE
    assert port_socket.bind.call_args_list == [call(("", 4001)), call(("", 4000))]
    port_socket.close.assert_called_once_with()


def test_get_free_port_range_resampled(monkeypatch, port_socket):
    monkeypatch.setattr(helper, "_port_range", range(4000, 4002))
    sample = Mock(side_effect=[[4000, 4001], [4001, 4000]])
    monkeypatch.setattr(helper.random, "sample", sample)
    port_socket.getsockname.side_effect = [("", 4001), ("", 4000)]

    assert helper.get_free_port() == 4001
    assert helper.get_free_port() == 4000

    assert sample.call_count == 2
    assert port_socket.bind.call_args_list == [call(("", 4001)), call(("", 4000))]


@pytest.mark.parametrize("error", [errno.EACCES, errno.EMFILE])
def test_get_free_port_range_bind_error(monkeypatch, port_socket, error):
    monkeypatch.setattr(helper, "_port_range", range(4000, 4002))
    monkeypatch.setattr(helper.random, "sample", lambda ports, count: list(ports))
    port_socket.bind.side_effect = OSError(error, "bind failed")

    with pytest.raises(OSError) as excinfo:
        helper.get_free_port()

    assert excinfo.value.errno == error
    port_socket.bind.assert_called_once_with(("", 4001))
    port_socket.close.assert_called_once_with()


@pytest.mark.parametrize("value", ["1-1000", "4000-4999", "64536-65535", "1-65535"])
def test_parse_port_range(value):
    start, end = (int(part) for part in value.split("-"))
    assert exporter.parse_port_range(value) == range(start, end + 1)


@pytest.mark.parametrize(
    "value",
    ["4000", "4000:5000", "a-b", "4000-5000-6000", "0-1000", "64536-65536", "5000-4000", "4000-4998"],
)
def test_exporter_invalid_port_range(monkeypatch, capsys, value):
    monkeypatch.setattr(sys, "argv", ["labgrid-exporter", f"--port-range={value}", "exports.yaml"])

    with pytest.raises(SystemExit) as excinfo:
        exporter.main()

    assert excinfo.value.code == 2
    assert "argument --port-range:" in capsys.readouterr().err


@pytest.mark.parametrize("args, expected", [(["--port-range=4000-5000"], range(4000, 5001)), ([], None)])
def test_exporter_port_range(monkeypatch, port_socket, args, expected):
    monkeypatch.setattr(helper, "_port_range", range(6000, 7001))
    monkeypatch.setattr(sys, "argv", ["labgrid-exporter", *args, "exports.yaml"])
    monkeypatch.setattr(exporter, "reexec", False)
    monkeypatch.setattr(exporter.asyncio, "run", lambda coroutine, **kwargs: coroutine.close())
    monkeypatch.setattr(exporter.asyncio, "set_event_loop", lambda loop: None)
    loop = asyncio.new_event_loop()
    monkeypatch.setattr(exporter.asyncio, "new_event_loop", lambda: loop)
    try:
        exporter.main()
    finally:
        loop.close()

    assert helper._port_range == expected
    monkeypatch.setattr(helper.random, "sample", lambda ports, count: list(ports))
    port_socket.getsockname.return_value = ("", 5000)

    assert exporter.get_free_port() == 5000
    assert ssh.get_free_port() == 5000
    port = 5000 if expected is not None else 0
    assert port_socket.bind.call_args_list == [call(("", port)), call(("", port))]
