"""Tests for the LG_SERIAL_TRACE_DIR feature in labgrid-exporter."""

import asyncio
import logging
import subprocess
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from labgrid.remote import exporter
from labgrid.remote.exporter import Exporter, ResourceExport, SerialPortExport


@pytest.fixture
def trace_args():
    """Return a builder bound to whatever LG_SERIAL_TRACE_DIR is set."""

    def _build(group_name="bbb", resource_name="console", client_identity="okaro/sjg", path="/dev/ttyUSB0"):
        return SerialPortExport._build_trace_args(group_name, resource_name, client_identity, path)

    return _build


def test_returns_empty_when_env_unset(trace_args, monkeypatch):
    monkeypatch.delenv("LG_SERIAL_TRACE_DIR", raising=False)
    assert trace_args() == []


def test_builds_yaml_args(trace_args, monkeypatch, tmp_path):
    monkeypatch.setenv("LG_SERIAL_TRACE_DIR", str(tmp_path))
    args = trace_args(group_name="bbb", resource_name="console", client_identity="okaro/sjg")
    assert args == [
        "-Y",
        f"    trace-both: {tmp_path}/bbb-console-okaro_sjg.log",
        "-Y",
        "    trace-both-timestamp: true",
    ]


def test_creates_missing_directory(trace_args, monkeypatch, tmp_path):
    target = tmp_path / "newdir"
    assert not target.exists()
    monkeypatch.setenv("LG_SERIAL_TRACE_DIR", str(target))
    trace_args()
    assert target.is_dir()

    # An existing directory is fine too
    assert trace_args()


def test_unusable_directory(trace_args, monkeypatch, tmp_path, caplog):
    """A directory which cannot be created disables tracing, with a warning"""
    (tmp_path / "file").write_text("")
    monkeypatch.setenv("LG_SERIAL_TRACE_DIR", str(tmp_path / "file" / "trace"))
    with caplog.at_level(logging.WARNING):
        assert trace_args() == []
    assert "Not tracing /dev/ttyUSB0: cannot create LG_SERIAL_TRACE_DIR" in caplog.text


def test_user_slashes_rewritten(trace_args, monkeypatch, tmp_path):
    monkeypatch.setenv("LG_SERIAL_TRACE_DIR", str(tmp_path))
    args = trace_args(client_identity="myhost/alice")
    assert args[1] == f"    trace-both: {tmp_path}/bbb-console-myhost_alice.log"


@pytest.mark.parametrize(
    "client_identity,label",
    [
        # YAML metacharacters would break the ser2net configuration
        ("host/a: b", "host_a__b"),
        ("host/a #b", "host_a__b"),
        ("host/'a\"", "host__a_"),
        # ser2net expands backslash escapes in filenames, e.g. \x2f is '/'
        ("host/x\\x2f..\\x2fetc", "host_x_x2f.._x2fetc"),
        ("host/\\Y", "host__Y"),
    ],
)
def test_hostile_identity(trace_args, monkeypatch, tmp_path, client_identity, label):
    """The client chooses its identity, so it must be made safe"""
    monkeypatch.setenv("LG_SERIAL_TRACE_DIR", str(tmp_path))
    args = trace_args(client_identity=client_identity)
    path = f"{tmp_path}/bbb-console-{label}.log"
    assert args[1] == f"    trace-both: {path}"
    assert yaml.safe_load(args[1]) == {"trace-both": path}


def test_resources_have_separate_files(trace_args, monkeypatch, tmp_path):
    """Two serial ports on the same board must not share a trace"""
    monkeypatch.setenv("LG_SERIAL_TRACE_DIR", str(tmp_path))
    assert trace_args(resource_name="console")[1] != trace_args(resource_name="uart2")[1]


def test_unknown_user_when_none(trace_args, monkeypatch, tmp_path):
    monkeypatch.setenv("LG_SERIAL_TRACE_DIR", str(tmp_path))
    args = trace_args(client_identity=None)
    assert args[1] == f"    trace-both: {tmp_path}/bbb-console-unknown.log"


def test_falls_back_to_path_basename(trace_args, monkeypatch, tmp_path):
    monkeypatch.setenv("LG_SERIAL_TRACE_DIR", str(tmp_path))
    args = trace_args(group_name="", resource_name="", path="/dev/ttyUSB7")
    assert args[1] == f"    trace-both: {tmp_path}/ttyUSB7-okaro_sjg.log"


def test_hexdump_disabled_by_default(trace_args, monkeypatch, tmp_path):
    monkeypatch.setenv("LG_SERIAL_TRACE_DIR", str(tmp_path))
    monkeypatch.delenv("LG_SERIAL_TRACE_HEXDUMP", raising=False)
    args = trace_args()
    assert "    trace-both-hexdump: true" not in args


def test_hexdump_enabled_when_set(trace_args, monkeypatch, tmp_path):
    monkeypatch.setenv("LG_SERIAL_TRACE_DIR", str(tmp_path))
    monkeypatch.setenv("LG_SERIAL_TRACE_HEXDUMP", "1")
    args = trace_args()
    assert args[-2:] == ["-Y", "    trace-both-hexdump: true"]


def test_hexdump_not_enabled_when_other_value(trace_args, monkeypatch, tmp_path):
    monkeypatch.setenv("LG_SERIAL_TRACE_DIR", str(tmp_path))
    monkeypatch.setenv("LG_SERIAL_TRACE_HEXDUMP", "true")
    args = trace_args()
    assert "    trace-both-hexdump: true" not in args


@pytest.mark.parametrize("client_identity", ["okaro/sjg", None])
def test_acquire_records_client_identity(client_identity):
    """acquire() stores the client identity sent by the coordinator"""
    resource = MagicMock(spec=ResourceExport)
    resource.acquired = None
    exporter = SimpleNamespace(groups={"bbb": {"serial": resource}}, update_resource=AsyncMock())
    asyncio.run(Exporter.acquire(exporter, "bbb", "serial", "place", client_identity))
    assert resource.client_identity == client_identity
    resource.acquire.assert_called_once_with("place")


def start_ser2net(monkeypatch, version):
    """Run SerialPortExport._start() with a fake ser2net of the given version

    Returns:
        list of str: The ser2net command line
    """
    child = MagicMock()
    child.wait.side_effect = subprocess.TimeoutExpired("ser2net", 0.5)
    popen = MagicMock(return_value=child)
    monkeypatch.setattr(
        exporter.subprocess,
        "run",
        MagicMock(return_value=SimpleNamespace(stdout=f"ser2net version {version}\n", returncode=0)),
    )
    monkeypatch.setattr(exporter.subprocess, "Popen", popen)
    export = SimpleNamespace(
        local=SimpleNamespace(avail=True, speed=115200),
        child=None,
        ser2net_bin="ser2net",
        logger=logging.getLogger("test"),
        group_name="bbb",
        resource_name="console",
        client_identity="okaro/sjg",
        _build_trace_args=SerialPortExport._build_trace_args,
    )
    SerialPortExport._start(export, {"path": "/dev/ttyUSB0"})
    return popen.call_args[0][0]


def test_start_traces(monkeypatch, tmp_path):
    """ser2net is asked to trace the port"""
    monkeypatch.setenv("LG_SERIAL_TRACE_DIR", str(tmp_path))
    cmd = start_ser2net(monkeypatch, "4.6.0")
    assert f"    trace-both: {tmp_path}/bbb-console-okaro_sjg.log" in cmd


def test_start_old_ser2net(monkeypatch, tmp_path, caplog):
    """An old ser2net cannot trace, so a warning is logged"""
    monkeypatch.setenv("LG_SERIAL_TRACE_DIR", str(tmp_path))
    with caplog.at_level(logging.WARNING):
        cmd = start_ser2net(monkeypatch, "3.5.1")
    assert not any("trace" in arg for arg in cmd)
    assert "Not tracing /dev/ttyUSB0: LG_SERIAL_TRACE_DIR needs ser2net 4.2.0 or later, not 3.5.1" in caplog.text
