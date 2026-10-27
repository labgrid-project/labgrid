import pytest

from labgrid.exceptions import InvalidConfigError
from labgrid.remote.config import ResourceConfig
from labgrid.util.usbhub import USBHubs

HUBS = {
    "a": {
        "base": "pci-0000:00:14.0-usb-0:10",
        "ports": {1: "2.1", 2: "2.2", 14: "1.2"},
    },
    "b": {"base": "pci-0000:04:00.0-usb-0:2", "ports": {"7": "2.3"}},
}


def test_path():
    hubs = USBHubs(HUBS)
    assert hubs.path("a", 1) == "pci-0000:00:14.0-usb-0:10.2.1"
    assert hubs.path("a", 14) == "pci-0000:00:14.0-usb-0:10.1.2"
    assert hubs.path("b", 7) == "pci-0000:04:00.0-usb-0:2.2.3"


def test_path_iface():
    hubs = USBHubs(HUBS)
    assert hubs.path("a", 2, "1.0") == "pci-0000:00:14.0-usb-0:10.2.2:1.0"
    assert hubs.path("a", 2, "1.1") == "pci-0000:00:14.0-usb-0:10.2.2:1.1"


def test_port_types():
    """Port numbers can be integers or strings, in either place"""
    hubs = USBHubs(HUBS)
    assert hubs.path("a", "1") == hubs.path("a", 1)
    assert hubs.path("b", 7) == hubs.path("b", "7")


def test_undefined():
    hubs = USBHubs(HUBS, "hubs.yaml")
    with pytest.raises(
        InvalidConfigError, match="hubs.yaml: hub 'z' is not defined"
    ):
        hubs.path("z", 1)
    with pytest.raises(
        InvalidConfigError, match="port 99 is not defined on hub 'a'"
    ):
        hubs.path("a", 99)
    with pytest.raises(
        InvalidConfigError, match="port left is not defined on hub 'a'"
    ):
        hubs.path("a", "left")


@pytest.mark.parametrize(
    "hubs,msg",
    [
        (["a"], "expected a mapping of hub names"),
        ({"a": "pci-0:2"}, "hub 'a' must be a mapping"),
        ({"a": {"ports": {1: "1.1"}}}, "hub 'a' needs a 'base' string"),
        ({"a": {"base": "pci-0:2"}}, "hub 'a' needs a 'ports' mapping"),
        (
            {"a": {"base": "pci-0:2", "ports": {1: 1.1}}},
            "hub 'a' port 1: suffix 1.1 must be a quoted string",
        ),
    ],
)
def test_invalid(hubs, msg):
    with pytest.raises(InvalidConfigError, match=msg):
        USBHubs(hubs)


def test_from_file(tmp_path):
    hubs_file = tmp_path / "hubs.yaml"
    hubs_file.write_text(
        """
a:
  base: 'pci-0000:00:14.0-usb-0:10'
  ports:
    1: '2.1'
    10: '1.10'
"""
    )
    hubs = USBHubs.from_file(str(hubs_file))
    assert hubs.path("a", 10) == "pci-0000:00:14.0-usb-0:10.1.10"


def test_unquoted_suffix(tmp_path):
    """An unquoted suffix is read as a number, so must be rejected"""
    hubs_file = tmp_path / "hubs.yaml"
    hubs_file.write_text("a:\n  base: 'pci-0:2'\n  ports:\n    10: 1.10\n")
    with pytest.raises(InvalidConfigError, match="must be a quoted string"):
        USBHubs.from_file(str(hubs_file))


def test_exporter_template(tmp_path):
    """The exporter configuration can use usb_hubs() to build each path"""
    (tmp_path / "hubs.yaml").write_text(
        """
a:
  base: 'pci-0000:00:14.0-usb-0:10'
  ports:
    2: '2.2'
    14: '1.2'
"""
    )
    config = tmp_path / "exporter.yaml"
    config.write_text(
        """
# set hub = usb_hubs('hubs.yaml')
board1:
  USBSerialPort:
    match:
      '@ID_PATH': '{{ hub.path('a', 2, '1.0') }}'
  HIDRelay:
    index: 4
    match:
      ID_PATH: '{{ hub.path('a', 14) }}'
  USBSDMuxDevice:
    match:
      '@ID_PATH': '{{ hub.path('a', 2) }}'
"""
    )
    data = ResourceConfig(str(config)).data
    assert data["board1"]["USBSerialPort"]["match"] == {
        "@ID_PATH": "pci-0000:00:14.0-usb-0:10.2.2:1.0"
    }
    assert data["board1"]["HIDRelay"]["match"] == {
        "ID_PATH": "pci-0000:00:14.0-usb-0:10.1.2"
    }
    assert data["board1"]["USBSDMuxDevice"]["match"] == {
        "@ID_PATH": "pci-0000:00:14.0-usb-0:10.2.2"
    }


def test_exporter_template_undefined(tmp_path):
    """A typo in the exporter configuration gives an error, not a bad path"""
    (tmp_path / "hubs.yaml").write_text(
        "a:\n  base: 'pci-0:2'\n  ports:\n    2: '2.2'\n"
    )
    config = tmp_path / "exporter.yaml"
    config.write_text(
        """
# set hub = usb_hubs('hubs.yaml')
board1:
  HIDRelay:
    match:
      ID_PATH: '{{ hub.path('a', 3) }}'
"""
    )
    with pytest.raises(
        InvalidConfigError, match="port 3 is not defined on hub 'a'"
    ):
        ResourceConfig(str(config))
