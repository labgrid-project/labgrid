"""Tests for USB hub expansion in the exporter config."""

import pytest

from labgrid.remote.exporter import _expand_hubs, ExporterError


def make_data(hubs, groups):
    """Build a config data dict with hubs and resource groups."""
    data = {}
    if hubs is not None:
        data["hubs"] = hubs
    data.update(groups)
    return data


class TestExpandHubs:
    def test_with_iface(self):
        """hub + port + iface produces @ID_PATH with interface suffix"""
        data = make_data(
            hubs={"a": {"base": "pci-0:2", "ports": {7: "2.3"}}},
            groups={"b": {"USBSerialPort": {"match": {"hub": "a", "port": 7, "iface": "1.0"}}}},
        )
        _expand_hubs(data)
        assert data["b"]["USBSerialPort"]["match"] == {"@ID_PATH": "pci-0:2.2.3:1.0"}
        assert "hubs" not in data

    def test_without_iface(self):
        """hub + port without iface produces ID_PATH (no @ prefix)"""
        data = make_data(
            hubs={"a": {"base": "pci-0:2", "ports": {7: "2.3"}}},
            groups={"b": {"HIDRelay": {"match": {"hub": "a", "port": 7}}}},
        )
        _expand_hubs(data)
        assert data["b"]["HIDRelay"]["match"] == {"ID_PATH": "pci-0:2.2.3"}

    def test_multiple_hubs(self):
        data = make_data(
            hubs={
                "a": {"base": "pci-0:2", "ports": {1: "1.1"}},
                "b": {"base": "pci-1:1", "ports": {3: "3.1"}},
            },
            groups={
                "b1": {"R": {"match": {"hub": "a", "port": 1, "iface": "1.0"}}},
                "b2": {"R": {"match": {"hub": "b", "port": 3, "iface": "1.0"}}},
            },
        )
        _expand_hubs(data)
        assert data["b1"]["R"]["match"]["@ID_PATH"] == "pci-0:2.1.1:1.0"
        assert data["b2"]["R"]["match"]["@ID_PATH"] == "pci-1:1.3.1:1.0"

    def test_mixed_iface_and_no_iface(self):
        """Serial port with iface and relay without, on the same hub"""
        data = make_data(
            hubs={"a": {"base": "pci-0:2", "ports": {1: "1.1", 2: "1.2"}}},
            groups={
                "b": {
                    "USBSerialPort": {"match": {"hub": "a", "port": 1, "iface": "1.0"}},
                    "HIDRelay": {"match": {"hub": "a", "port": 2}},
                }
            },
        )
        _expand_hubs(data)
        assert data["b"]["USBSerialPort"]["match"] == {"@ID_PATH": "pci-0:2.1.1:1.0"}
        assert data["b"]["HIDRelay"]["match"] == {"ID_PATH": "pci-0:2.1.2"}

    def test_string_port_keys(self):
        data = make_data(
            hubs={"a": {"base": "pci-0:2", "ports": {"7": "2.3"}}},
            groups={"g": {"R": {"match": {"hub": "a", "port": 7}}}},
        )
        _expand_hubs(data)
        assert data["g"]["R"]["match"]["ID_PATH"] == "pci-0:2.2.3"

    def test_integer_port_keys(self):
        data = make_data(
            hubs={"a": {"base": "pci-0:2", "ports": {7: "2.3"}}},
            groups={"g": {"R": {"match": {"hub": "a", "port": "7"}}}},
        )
        _expand_hubs(data)
        assert data["g"]["R"]["match"]["ID_PATH"] == "pci-0:2.2.3"

    def test_preserves_other_match_keys(self):
        data = make_data(
            hubs={"a": {"base": "pci-0:2", "ports": {1: "1.1"}}},
            groups={"g": {"R": {"match": {
                "hub": "a", "port": 1, "iface": "1.0", "ID_SERIAL_SHORT": "ABC",
            }}}},
        )
        _expand_hubs(data)
        match = data["g"]["R"]["match"]
        assert match["@ID_PATH"] == "pci-0:2.1.1:1.0"
        assert match["ID_SERIAL_SHORT"] == "ABC"
        assert "hub" not in match
        assert "port" not in match
        assert "iface" not in match

    def test_no_hubs_section(self):
        data = make_data(
            hubs=None,
            groups={"g": {"R": {"match": {"@ID_PATH": "foo"}}}},
        )
        _expand_hubs(data)
        assert data["g"]["R"]["match"]["@ID_PATH"] == "foo"

    def test_no_hub_references(self):
        data = make_data(
            hubs={"a": {"base": "pci-0:2", "ports": {1: "1.1"}}},
            groups={"g": {"R": {"match": {"@ID_PATH": "manual"}}}},
        )
        _expand_hubs(data)
        assert data["g"]["R"]["match"]["@ID_PATH"] == "manual"

    def test_undefined_hub(self):
        data = make_data(
            hubs={"a": {"base": "pci-0:2", "ports": {1: "1.1"}}},
            groups={"g": {"R": {"match": {"hub": "z", "port": 1}}}},
        )
        with pytest.raises(ExporterError, match="hub 'z' is not defined"):
            _expand_hubs(data)

    def test_undefined_port(self):
        data = make_data(
            hubs={"a": {"base": "pci-0:2", "ports": {1: "1.1"}}},
            groups={"g": {"R": {"match": {"hub": "a", "port": 99}}}},
        )
        with pytest.raises(ExporterError, match="port 99 is not defined"):
            _expand_hubs(data)

    def test_hub_without_port(self):
        data = make_data(
            hubs={"a": {"base": "pci-0:2", "ports": {1: "1.1"}}},
            groups={"g": {"R": {"match": {"hub": "a"}}}},
        )
        with pytest.raises(ExporterError, match="must both be specified"):
            _expand_hubs(data)

    def test_port_without_hub(self):
        data = make_data(
            hubs={"a": {"base": "pci-0:2", "ports": {1: "1.1"}}},
            groups={"g": {"R": {"match": {"port": 1}}}},
        )
        with pytest.raises(ExporterError, match="must both be specified"):
            _expand_hubs(data)

    def test_location_skipped(self):
        data = make_data(
            hubs={"a": {"base": "pci-0:2", "ports": {1: "1.1"}}},
            groups={"g": {"location": "lab", "R": {"match": {"hub": "a", "port": 1}}}},
        )
        _expand_hubs(data)
        assert data["g"]["R"]["match"]["ID_PATH"] == "pci-0:2.1.1"

    def test_hubs_removed_from_data(self):
        data = make_data(
            hubs={"a": {"base": "pci-0:2", "ports": {1: "1.1"}}},
            groups={"g": {"R": {"match": {"hub": "a", "port": 1}}}},
        )
        _expand_hubs(data)
        assert "hubs" not in data

    def test_iface_different_values(self):
        data = make_data(
            hubs={"a": {"base": "pci-0:2", "ports": {1: "1.1"}}},
            groups={"g": {
                "s0": {"match": {"hub": "a", "port": 1, "iface": "1.0"}},
                "s1": {"match": {"hub": "a", "port": 1, "iface": "1.1"}},
            }},
        )
        _expand_hubs(data)
        assert data["g"]["s0"]["match"]["@ID_PATH"] == "pci-0:2.1.1:1.0"
        assert data["g"]["s1"]["match"]["@ID_PATH"] == "pci-0:2.1.1:1.1"

    def test_invalid_port_type(self):
        data = make_data(
            hubs={"a": {"base": "pci-0:2", "ports": {1: "1.1"}}},
            groups={"g": {"R": {"match": {"hub": "a", "port": "abc"}}}},
        )
        with pytest.raises(ExporterError, match="port abc is not defined"):
            _expand_hubs(data)

    def test_missing_base(self):
        data = make_data(
            hubs={"a": {"ports": {1: "1.1"}}},
            groups={"g": {"R": {"match": {"hub": "a", "port": 1}}}},
        )
        with pytest.raises(ExporterError, match="must have either 'base' or both 'parent' and 'port'"):
            _expand_hubs(data)


class TestNestedHubs:
    def test_parent_hub(self):
        """A child hub inherits its base from a parent hub + port"""
        data = make_data(
            hubs={
                "c": {"base": "pci-0:5", "ports": {14: "1.2"}},
                "ykush0": {"parent": "c", "port": 14, "ports": {2: "2"}},
            },
            groups={"g": {"SunxiUSBLoader": {"match": {"hub": "ykush0", "port": 2}}}},
        )
        _expand_hubs(data)
        assert data["g"]["SunxiUSBLoader"]["match"] == {"ID_PATH": "pci-0:5.1.2.2"}

    def test_parent_hub_with_iface(self):
        """Child hub with iface produces @ID_PATH"""
        data = make_data(
            hubs={
                "c": {"base": "pci-0:5", "ports": {14: "1.2"}},
                "ykush0": {"parent": "c", "port": 14, "ports": {1: "1"}},
            },
            groups={"g": {"USBSerialPort": {"match": {
                "hub": "ykush0", "port": 1, "iface": "1.0",
            }}}},
        )
        _expand_hubs(data)
        assert data["g"]["USBSerialPort"]["match"] == {"@ID_PATH": "pci-0:5.1.2.1:1.0"}

    def test_three_levels_deep(self):
        """Hub behind a hub behind a hub"""
        data = make_data(
            hubs={
                "root": {"base": "pci-0:1", "ports": {1: "1.1"}},
                "mid": {"parent": "root", "port": 1, "ports": {3: "3"}},
                "leaf": {"parent": "mid", "port": 3, "ports": {2: "2"}},
            },
            groups={"g": {"R": {"match": {"hub": "leaf", "port": 2}}}},
        )
        _expand_hubs(data)
        assert data["g"]["R"]["match"] == {"ID_PATH": "pci-0:1.1.1.3.2"}

    def test_circular_reference(self):
        data = make_data(
            hubs={
                "a": {"parent": "b", "port": 1, "ports": {1: "1"}},
                "b": {"parent": "a", "port": 1, "ports": {1: "1"}},
            },
            groups={"g": {"R": {"match": {"hub": "a", "port": 1}}}},
        )
        with pytest.raises(ExporterError, match="circular hub reference"):
            _expand_hubs(data)

    def test_parent_undefined(self):
        data = make_data(
            hubs={"child": {"parent": "missing", "port": 1, "ports": {1: "1"}}},
            groups={"g": {"R": {"match": {"hub": "child", "port": 1}}}},
        )
        with pytest.raises(ExporterError, match="hub 'missing' is not defined"):
            _expand_hubs(data)

    def test_parent_port_undefined(self):
        data = make_data(
            hubs={
                "c": {"base": "pci-0:5", "ports": {1: "1.1"}},
                "child": {"parent": "c", "port": 99, "ports": {1: "1"}},
            },
            groups={"g": {"R": {"match": {"hub": "child", "port": 1}}}},
        )
        with pytest.raises(ExporterError, match="port 99 is not defined in parent hub 'c'"):
            _expand_hubs(data)

    def test_mixed_parent_and_base_hubs(self):
        """Some hubs use base, others use parent — both in the same config"""
        data = make_data(
            hubs={
                "a": {"base": "pci-0:10", "ports": {2: "2.2"}},
                "c": {"base": "pci-0:5", "ports": {14: "1.2"}},
                "ykush0": {"parent": "c", "port": 14, "ports": {2: "2"}},
            },
            groups={"g": {
                "serial": {"match": {"hub": "a", "port": 2, "iface": "1.0"}},
                "loader": {"match": {"hub": "ykush0", "port": 2}},
            }},
        )
        _expand_hubs(data)
        assert data["g"]["serial"]["match"] == {"@ID_PATH": "pci-0:10.2.2:1.0"}
        assert data["g"]["loader"]["match"] == {"ID_PATH": "pci-0:5.1.2.2"}
