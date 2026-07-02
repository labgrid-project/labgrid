import warnings

import pexpect
import pytest

from labgrid.remote.common import get_metadata_single_value_by_key


def test_client_help():
    with pexpect.spawn("python -m labgrid.remote.client --help") as spawn:
        spawn.expect("usage")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0
        assert spawn.signalstatus is None


def test_exporter_help():
    with pexpect.spawn("python -m labgrid.remote.exporter --help") as spawn:
        spawn.expect("usage")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0
        assert spawn.signalstatus is None


def test_exporter_start_coordinator_unreachable(monkeypatch, tmpdir):
    monkeypatch.setenv("LG_COORDINATOR", "coordinator.invalid")

    config = "exports.yaml"
    p = tmpdir.join(config)
    p.write(
        """
    Testport:
        NetworkSerialPort:
          host: 'localhost'
          port: 4000
    """
    )

    with pexpect.spawn(f"python -m labgrid.remote.exporter {config}", cwd=tmpdir) as spawn:
        spawn.expect("coordinator is unavailable", timeout=10)
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 100, spawn.before


def test_exporter_coordinator_becomes_unreachable(coordinator, exporter):
    coordinator.suspend_tree()

    exporter.spawn.expect(pexpect.EOF, timeout=30)
    exporter.spawn.close()
    assert exporter.exitstatus == 100

    coordinator.resume_tree()


def test_get_metadata_single_value_by_key_returns_value_for_existing_key():
    metadata = [("key1", "value1"), ("key2", "value2")]
    assert get_metadata_single_value_by_key(metadata, "key1") == "value1"
    assert get_metadata_single_value_by_key(metadata, "key2") == "value2"


def test_get_metadata_single_value_by_key_returns_none_for_missing_key():
    metadata = [("key1", "value1")]
    assert get_metadata_single_value_by_key(metadata, "other") is None


def test_get_metadata_single_value_by_key_returns_none_for_empty_metadata():
    assert get_metadata_single_value_by_key((), "key") is None


def test_get_metadata_single_value_by_key_returns_none_for_none_metadata():
    assert get_metadata_single_value_by_key(None, "key") is None


def test_get_metadata_single_value_by_key_returns_first_value_on_duplicate_keys():
    metadata = [("key", "first"), ("key", "second")]
    with pytest.warns(UserWarning, match="Multiple metadata KV pairs"):
        result = get_metadata_single_value_by_key(metadata, "key")
        assert result == "first"


def test_get_metadata_single_value_by_key_no_warning_on_single_match():
    metadata = [("key", "value")]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        get_metadata_single_value_by_key(metadata, "key")
        assert len(caught) == 0


def test_get_metadata_single_value_by_key_returns_first_value_for_non_adjacent_duplicates():
    metadata = [("key", "first"), ("other", "value"), ("key", "second")]
    with pytest.warns(UserWarning, match="Multiple metadata KV pairs"):
        result = get_metadata_single_value_by_key(metadata, "key")
        assert result == "first"


def test_get_metadata_single_value_by_key_is_case_sensitive():
    metadata = [("Key", "value")]
    assert get_metadata_single_value_by_key(metadata, "key") is None
    assert get_metadata_single_value_by_key(metadata, "Key") == "value"
