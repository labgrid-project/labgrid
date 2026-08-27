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
            hubs={"a": {"base": "pci-0000:04:00.0-usb-0:2", "ports": {7: "2.3"}}},
            groups={
                "board1": {
                    "USBSerialPort": {
                        "match": {
                            "hub": "a",
                            "port": 7,
                            "iface": "1.0",
                        }
                    }
                }
            },
        )
        _expand_hubs(data)
        assert data["board1"]["USBSerialPort"]["match"] == {
            "@ID_PATH": "pci-0000:04:00.0-usb-0:2.2.3:1.0",
        }
        assert "hubs" not in data

    def test_without_iface(self):
        """hub + port without iface produces ID_PATH (no @ prefix)"""
        data = make_data(
            hubs={"a": {"base": "pci-0000:04:00.0-usb-0:2", "ports": {7: "2.3"}}},
            groups={"board1": {"HIDRelay": {"match": {"hub": "a", "port": 7}}}},
        )
        _expand_hubs(data)
        assert data["board1"]["HIDRelay"]["match"] == {
            "ID_PATH": "pci-0000:04:00.0-usb-0:2.2.3",
        }

    def test_multiple_hubs(self):
        data = make_data(
            hubs={
                "a": {"base": "pci-0000:04:00.0-usb-0:2", "ports": {1: "1.1"}},
                "b": {"base": "pci-0000:05:00.0-usb-0:1", "ports": {3: "3.1"}},
            },
            groups={
                "board1": {
                    "USBSerialPort": {
                        "match": {
                            "hub": "a",
                            "port": 1,
                            "iface": "1.0",
                        }
                    }
                },
                "board2": {
                    "USBSerialPort": {
                        "match": {
                            "hub": "b",
                            "port": 3,
                            "iface": "1.0",
                        }
                    }
                },
            },
        )
        _expand_hubs(data)
        assert data["board1"]["USBSerialPort"]["match"]["@ID_PATH"] == "pci-0000:04:00.0-usb-0:2.1.1:1.0"
        assert data["board2"]["USBSerialPort"]["match"]["@ID_PATH"] == "pci-0000:05:00.0-usb-0:1.3.1:1.0"

    def test_mixed_iface_and_no_iface(self):
        """Serial port with iface and relay without, on the same hub"""
        data = make_data(
            hubs={"a": {"base": "pci-0:2", "ports": {1: "1.1", 2: "1.2"}}},
            groups={
                "board1": {
                    "USBSerialPort": {
                        "match": {
                            "hub": "a",
                            "port": 1,
                            "iface": "1.0",
                        }
                    },
                    "HIDRelay": {"match": {"hub": "a", "port": 2}},
                }
            },
        )
        _expand_hubs(data)
        assert data["board1"]["USBSerialPort"]["match"] == {
            "@ID_PATH": "pci-0:2.1.1:1.0",
        }
        assert data["board1"]["HIDRelay"]["match"] == {
            "ID_PATH": "pci-0:2.1.2",
        }

    def test_string_port_keys(self):
        """YAML may parse port keys as strings."""
        data = make_data(
            hubs={"a": {"base": "pci-0:2", "ports": {"7": "2.3"}}},
            groups={"g": {"R": {"match": {"hub": "a", "port": 7}}}},
        )
        _expand_hubs(data)
        assert data["g"]["R"]["match"]["ID_PATH"] == "pci-0:2.2.3"

    def test_integer_port_keys(self):
        """Port keys as integers with string port reference."""
        data = make_data(
            hubs={"a": {"base": "pci-0:2", "ports": {7: "2.3"}}},
            groups={"g": {"R": {"match": {"hub": "a", "port": "7"}}}},
        )
        _expand_hubs(data)
        assert data["g"]["R"]["match"]["ID_PATH"] == "pci-0:2.2.3"

    def test_preserves_other_match_keys(self):
        data = make_data(
            hubs={"a": {"base": "pci-0:2", "ports": {1: "1.1"}}},
            groups={
                "g": {
                    "R": {
                        "match": {
                            "hub": "a",
                            "port": 1,
                            "iface": "1.0",
                            "ID_SERIAL_SHORT": "ABC123",
                        }
                    }
                }
            },
        )
        _expand_hubs(data)
        match = data["g"]["R"]["match"]
        assert match["@ID_PATH"] == "pci-0:2.1.1:1.0"
        assert match["ID_SERIAL_SHORT"] == "ABC123"
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
        """Hubs defined but no resources reference them."""
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
        """The 'location' key is a string, not a dict — should not crash."""
        data = make_data(
            hubs={"a": {"base": "pci-0:2", "ports": {1: "1.1"}}},
            groups={
                "g": {
                    "location": "lab",
                    "R": {"match": {"hub": "a", "port": 1}},
                }
            },
        )
        _expand_hubs(data)
        assert data["g"]["R"]["match"]["ID_PATH"] == "pci-0:2.1.1"

    def test_hubs_removed_from_data(self):
        """The hubs section should not appear as a resource group."""
        data = make_data(
            hubs={"a": {"base": "pci-0:2", "ports": {1: "1.1"}}},
            groups={"g": {"R": {"match": {"hub": "a", "port": 1}}}},
        )
        _expand_hubs(data)
        assert "hubs" not in data

    def test_iface_different_values(self):
        """Different interface numbers for different resource types"""
        data = make_data(
            hubs={"a": {"base": "pci-0:2", "ports": {1: "1.1"}}},
            groups={
                "g": {
                    "serial0": {"match": {"hub": "a", "port": 1, "iface": "1.0"}},
                    "serial1": {"match": {"hub": "a", "port": 1, "iface": "1.1"}},
                }
            },
        )
        _expand_hubs(data)
        assert data["g"]["serial0"]["match"]["@ID_PATH"] == "pci-0:2.1.1:1.0"
        assert data["g"]["serial1"]["match"]["@ID_PATH"] == "pci-0:2.1.1:1.1"
