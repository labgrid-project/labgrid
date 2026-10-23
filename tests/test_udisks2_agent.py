import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest


def load_udisks2_agent(monkeypatch, device):
    client = SimpleNamespace(
        get_object=lambda path: SimpleNamespace(
            get_partition=lambda: SimpleNamespace(
                get_cached_property=lambda name: SimpleNamespace(
                    get_uint64=lambda: {
                        "Offset": 1048576,
                        "Size": 512 * 1024**2,
                    }[name],
                ),
            ),
        ),
        get_object_manager=lambda: SimpleNamespace(
            get_objects=lambda: (
                [
                    SimpleNamespace(get_block=lambda: None),
                    device,
                ]
                if device is not None
                else []
            )
        ),
    )
    udisks = SimpleNamespace(Client=SimpleNamespace(new_sync=Mock(return_value=client)))
    glib = SimpleNamespace(Variant=lambda signature, value: (signature, value))
    repository = ModuleType("gi.repository")
    repository.GLib = glib
    repository.UDisks = udisks
    gi = ModuleType("gi")
    gi.require_version = Mock()
    gi.repository = repository
    monkeypatch.setitem(sys.modules, "gi", gi)
    monkeypatch.setitem(sys.modules, "gi.repository", repository)

    agent_path = Path(__file__).parents[1] / "labgrid" / "util" / "agents" / "udisks2.py"
    spec = importlib.util.spec_from_file_location("test_udisks2_agent", agent_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("filesystem", ["vfat", "ext4"])
@pytest.mark.parametrize("table_type", ["dos", "gpt"])
def test_partition_operations(monkeypatch, filesystem, table_type):
    partition_table = SimpleNamespace(
        call_create_partition_and_format_sync=Mock(return_value="/partition"),
        get_cached_property=lambda name: SimpleNamespace(get_string=lambda: table_type),
    )
    block = SimpleNamespace(
        call_format_sync=Mock(),
        get_cached_property=lambda name: SimpleNamespace(get_bytestring=lambda: b"/dev/test"),
    )
    device = SimpleNamespace(
        get_block=lambda: block,
        get_partition_table=lambda: partition_table,
    )
    agent = load_udisks2_agent(monkeypatch, device)

    agent._devs["old"] = object()
    agent.handle_create_partition_table("/dev/test", table_type)
    assert agent._devs == {}
    assert agent.handle_has_partition_table("/dev/test")
    agent._devs["old"] = object()
    end = agent.handle_create_partition_and_format(
        "/dev/test",
        filesystem,
        "UPDATE",
        2 * 1048576,
        512 * 1024**2,
    )
    assert end == 513 * 1024**2

    block.call_format_sync.assert_called_once_with(table_type, ("a{sv}", {}), None)
    args = partition_table.call_create_partition_and_format_sync.call_args.args
    assert args[:6] == (
        2 * 1048576,
        512 * 1024**2,
        "",
        "",
        ("a{sv}", {"partition-type": ("s", "primary")} if table_type == "dos" else {}),
        filesystem,
    )
    options = {"label": ("s", "UPDATE")}
    if filesystem == "vfat":
        options["mkfs-args"] = ("as", ["-F", "32"])
    else:
        options["take-ownership"] = ("b", True)
    assert args[6] == ("a{sv}", options)
    assert args[7] is None
    assert agent._devs == {}


def test_missing_device(monkeypatch):
    agent = load_udisks2_agent(monkeypatch, None)
    assert agent.handle_has_partition_table("/dev/missing") is False
    with pytest.raises(ValueError, match="No udisks2 device"):
        agent.handle_create_partition_table("/dev/missing")
    with pytest.raises(ValueError, match="No udisks2 device"):
        agent.handle_create_partition_and_format("/dev/missing")
    with pytest.raises(ValueError, match="No udisks2 device"):
        agent.UDisks2Device("/dev/missing")._setup()


def test_missing_partition_table(monkeypatch):
    block = SimpleNamespace(
        get_cached_property=lambda name: SimpleNamespace(get_bytestring=lambda: b"/dev/test"),
    )
    device = SimpleNamespace(get_block=lambda: block, get_partition_table=lambda: None)
    agent = load_udisks2_agent(monkeypatch, device)
    assert agent.handle_has_partition_table("/dev/test") is False
    with pytest.raises(ValueError, match="No partition table"):
        agent.handle_create_partition_and_format("/dev/test")


def test_format_error_invalidates_cache(monkeypatch):
    block = SimpleNamespace(
        call_format_sync=Mock(side_effect=RuntimeError("permission denied")),
        get_cached_property=lambda name: SimpleNamespace(get_bytestring=lambda: b"/dev/test"),
    )
    device = SimpleNamespace(get_block=lambda: block)
    agent = load_udisks2_agent(monkeypatch, device)
    agent._devs["old"] = object()
    with pytest.raises(RuntimeError, match="permission denied"):
        agent.handle_create_partition_table("/dev/test")
    assert agent._devs == {}


def test_mount_setup(monkeypatch):
    filesystem = object()
    block = SimpleNamespace(
        get_cached_property=lambda name: SimpleNamespace(get_bytestring=lambda: b"/dev/test"),
    )
    device = SimpleNamespace(
        get_block=lambda: block,
        get_filesystem=lambda: filesystem,
    )
    agent = load_udisks2_agent(monkeypatch, device)
    dev = agent.UDisks2Device("/dev/test")
    dev._setup()
    assert dev.fs is filesystem


def test_mount_setup_without_filesystem(monkeypatch):
    block = SimpleNamespace(
        get_cached_property=lambda name: SimpleNamespace(get_bytestring=lambda: b"/dev/test"),
    )
    device = SimpleNamespace(get_block=lambda: block, get_filesystem=lambda: None)
    agent = load_udisks2_agent(monkeypatch, device)

    with pytest.raises(ValueError, match="no filesystem found"):
        agent.UDisks2Device("/dev/test")._setup()
