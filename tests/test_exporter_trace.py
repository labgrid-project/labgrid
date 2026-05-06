"""Tests for the LG_SERIAL_TRACE_DIR feature in labgrid-exporter."""

import pytest

from labgrid.remote.exporter import SerialPortExport


@pytest.fixture
def trace_args(monkeypatch):
    """Return a builder bound to whatever LG_SERIAL_TRACE_DIR is set."""

    def _build(group_name="bbb", user="okaro/sjg", path="/dev/ttyUSB0"):
        return SerialPortExport._build_trace_args(group_name, user, path)

    return _build


def test_returns_empty_when_env_unset(trace_args, monkeypatch):
    monkeypatch.delenv("LG_SERIAL_TRACE_DIR", raising=False)
    assert trace_args() == []


def test_builds_yaml_args(trace_args, monkeypatch, tmp_path):
    monkeypatch.setenv("LG_SERIAL_TRACE_DIR", str(tmp_path))
    args = trace_args(group_name="bbb", user="okaro/sjg")
    assert args == [
        "-Y",
        f"    trace-both: {tmp_path}/bbb-okaro_sjg.log",
        "-Y",
        "    trace-both-timestamp: true",
    ]


def test_creates_missing_directory(trace_args, monkeypatch, tmp_path):
    target = tmp_path / "newdir"
    assert not target.exists()
    monkeypatch.setenv("LG_SERIAL_TRACE_DIR", str(target))
    trace_args()
    assert target.is_dir()


def test_user_slashes_rewritten(trace_args, monkeypatch, tmp_path):
    monkeypatch.setenv("LG_SERIAL_TRACE_DIR", str(tmp_path))
    args = trace_args(user="myhost/alice")
    assert args[1] == f"    trace-both: {tmp_path}/bbb-myhost_alice.log"


def test_unknown_user_when_none(trace_args, monkeypatch, tmp_path):
    monkeypatch.setenv("LG_SERIAL_TRACE_DIR", str(tmp_path))
    args = trace_args(user=None)
    assert args[1] == f"    trace-both: {tmp_path}/bbb-unknown.log"


def test_falls_back_to_path_basename(trace_args, monkeypatch, tmp_path):
    monkeypatch.setenv("LG_SERIAL_TRACE_DIR", str(tmp_path))
    args = trace_args(group_name="", path="/dev/ttyUSB7")
    assert args[1] == f"    trace-both: {tmp_path}/ttyUSB7-okaro_sjg.log"


def test_existing_dir_is_reused(trace_args, monkeypatch, tmp_path):
    """If the dir already exists, makedirs(exist_ok=True) must not fail."""
    monkeypatch.setenv("LG_SERIAL_TRACE_DIR", str(tmp_path))
    trace_args()
    trace_args()  # second call would error if exist_ok wasn't honoured
