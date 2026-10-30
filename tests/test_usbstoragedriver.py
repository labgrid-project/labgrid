from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

import labgrid.driver.usbstoragedriver as usbstoragedriver
from labgrid.driver.exception import ExecutionError
from labgrid.driver.usbstoragedriver import USBStorageDriver
from labgrid.resource.common import ResourceManager
from labgrid.resource.remote import NetworkUSBMassStorage
from labgrid.resource.udev import USBMassStorage


@pytest.fixture
def storage_driver(target, monkeypatch):
    monkeypatch.setattr(USBMassStorage, "manager_cls", ResourceManager)
    USBMassStorage(
        target,
        name="storage",
        device=SimpleNamespace(device_node="/dev/test"),
    )
    driver = USBStorageDriver(target, name=None)
    driver.proxy = Mock()
    driver.proxy.has_partition_table.return_value = True
    driver.proxy.create_partition_and_format.return_value = 1024 * 1024 * 1024
    monkeypatch.setattr(driver, "_wait_for_medium", Mock())
    monkeypatch.setattr(driver, "_start_wrapper", Mock())
    target.activate(driver)
    yield driver
    target.deactivate(driver)


@pytest.mark.parametrize(
    "filesystem,label", [("vfat", "UPDATE"), ("ext4", "test")]
)
def test_format_uses_configured_single_partition(storage_driver, filesystem, label):
    storage_driver.partition_layout = usbstoragedriver._format_layout(
        {
            "partitions": [
                {"size": "remaining", "filesystem": filesystem, "label": label}
            ],
        }
    )

    storage_driver.format()

    assert storage_driver.devpath == "/dev/test"
    assert storage_driver.proxy.method_calls == [
        call.create_partition_table("/dev/test", "dos"),
        call.has_partition_table("/dev/test"),
        call.create_partition_and_format("/dev/test", filesystem, label, 1048576, 0),
    ]
    assert storage_driver._wait_for_medium.call_args_list == [
        call(None),
        call(1),
    ]


def test_format_defaults(storage_driver):
    storage_driver.format()
    storage_driver.proxy.create_partition_and_format.assert_called_once_with(
        "/dev/test", "vfat", "", 1048576, 0
    )


def test_format_partition_table_timeout(storage_driver, monkeypatch):
    timeout = SimpleNamespace(remaining=0.0)
    type_with_expiry = Mock(return_value=timeout)
    monkeypatch.setattr(usbstoragedriver, "Timeout", type_with_expiry)
    timeout.expired = True

    with pytest.raises(ExecutionError, match="partition table on /dev/test"):
        storage_driver.format()

    storage_driver.proxy.create_partition_and_format.assert_not_called()
    storage_driver._wait_for_medium.assert_called_once_with(None)


def test_format_waits_for_partition_table(storage_driver, monkeypatch):
    storage_driver.proxy.has_partition_table.side_effect = [False, True]
    sleep = Mock()
    monkeypatch.setattr(usbstoragedriver.time, "sleep", sleep)

    storage_driver.format()

    sleep.assert_called_once()
    assert storage_driver.proxy.has_partition_table.call_count == 2
    storage_driver.proxy.create_partition_and_format.assert_called_once()


def test_format_propagates_failure(storage_driver):
    storage_driver.proxy.create_partition_and_format.side_effect = RuntimeError(
        "failed"
    )
    with pytest.raises(RuntimeError, match="failed"):
        storage_driver.format()
    storage_driver._wait_for_medium.assert_called_once_with(None)


def test_configured_layout(storage_driver):
    storage_driver.partition_layout = usbstoragedriver._format_layout(
        {
            "partition_table": "gpt",
            "partitions": [
                {"size": "512MiB", "filesystem": "vfat", "label": "BOOT"},
                {"size": "remaining", "filesystem": "ext4", "label": "DATA"},
            ],
        }
    )
    storage_driver.proxy.create_partition_and_format.side_effect = [
        513 * 1024**2,
        4 * 1024**3,
    ]

    storage_driver.format()

    storage_driver.proxy.create_partition_table.assert_called_once_with(
        "/dev/test", "gpt"
    )
    assert storage_driver.proxy.create_partition_and_format.call_args_list == [
        call("/dev/test", "vfat", "BOOT", 1048576, 512 * 1024**2),
        call("/dev/test", "ext4", "DATA", 513 * 1024**2, 0),
    ]
    assert storage_driver._wait_for_medium.call_args_list == [
        call(None),
        call(1),
        call(2),
    ]


@pytest.mark.parametrize(
    "layout",
    [
        {"partitions": []},
        {"partitions": [{"size": "0MiB", "filesystem": "ext4"}]},
        {"partitions": [{"size": 123, "filesystem": "ext4"}]},
        {"partitions": [{"size": "1GiB", "filesystem": "ntfs"}]},
        {"partitions": [{"size": "1GiB", "filesystem": "ext4", "unknown": True}]},
        {
            "partition_table": "invalid",
            "partitions": [{"size": "remaining", "filesystem": "ext4"}],
        },
        {"partitions": [{"size": "remaining", "filesystem": "ext4"}] * 2},
        {"partitions": [{"size": "1GiB", "filesystem": "ext4"}] * 5},
    ],
)
def test_invalid_layout(layout):
    with pytest.raises((ValueError, TypeError)):
        usbstoragedriver._format_layout(layout)
