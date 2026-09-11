import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from opentelemetry import metrics

from labgrid.remote import otel_metrics
from labgrid.remote.common import ResourceEntry
from labgrid.remote.exporter import (
    BrokenResourceError,
    Exporter,
    InvalidResourceRequestError,
    ResourceExport,
    UnknownResourceError,
)
from labgrid.remote.generated import labgrid_coordinator_pb2 as pb2
from labgrid.remote.otel_exporter_metrics import record_resource_command, setup_exporter_metrics


@pytest.fixture(autouse=True)
def metrics_environment(monkeypatch):
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    monkeypatch.delenv("OTEL_METRICS_EXPORTER", raising=False)
    monkeypatch.setattr(otel_metrics, "_meter_provider", None)


@pytest.fixture
def metric_reader(monkeypatch):
    sdk = pytest.importorskip("opentelemetry.sdk.metrics")
    export = pytest.importorskip("opentelemetry.sdk.metrics.export")
    reader = export.InMemoryMetricReader()
    provider = sdk.MeterProvider(metric_readers=[reader])
    monkeypatch.setattr(metrics, "get_meter_provider", lambda: provider)
    assert otel_metrics.setup_metrics(None)
    yield reader
    provider.shutdown()


def measurements(reader):
    data = reader.get_metrics_data()
    if data is None:
        return {}
    return {
        metric.name: metric.data.data_points
        for resource in data.resource_metrics
        for scope in resource.scope_metrics
        for metric in scope.metrics
    }


def make_exporter():
    exporter = object.__new__(Exporter)
    exporter.groups = {}
    exporter.out_queue = asyncio.Queue()
    return exporter


def make_resource(cls, *, avail=True, acquired=None, broken=None):
    data = {"cls": cls, "params": {}, "avail": avail, "acquired": acquired}
    if broken:
        resource = ResourceExport(data)
        resource.broken = broken
        return resource
    return ResourceEntry(data)


def test_exporter_resource_gauges(metric_reader):
    exporter = make_exporter()
    setup_exporter_metrics(exporter)
    assert not measurements(metric_reader)

    free = make_resource("NetworkSerialPort")
    unavailable = make_resource("NetworkSerialPort", avail=False)
    acquired = make_resource("NetworkSerialPort", acquired="place")
    unavailable_acquired = make_resource("NetworkSerialPort", avail=False, acquired="place")
    broken = make_resource("NetworkSerialPort", broken="device failed")
    exporter.groups = {
        "serial": {"free": free, "unavailable": unavailable, "acquired": acquired},
        "extra": {"broken": broken, "unavailable-acquired": unavailable_acquired},
        "power": {"power": make_resource("NetworkPowerPort")},
    }

    def observed():
        return {
            name: {point.attributes["resource_class"]: point.value for point in points}
            for name, points in measurements(metric_reader).items()
        }

    expected = {
        "labgrid_exporter_resources_configured": {"NetworkSerialPort": 5, "NetworkPowerPort": 1},
        "labgrid_exporter_resources_free": {"NetworkSerialPort": 1, "NetworkPowerPort": 1},
        # Availability and acquisition are independent, so these can overlap.
        "labgrid_exporter_resources_unavailable": {"NetworkSerialPort": 2, "NetworkPowerPort": 0},
        "labgrid_exporter_resources_acquired": {"NetworkSerialPort": 2, "NetworkPowerPort": 0},
        "labgrid_exporter_resources_broken": {"NetworkSerialPort": 1, "NetworkPowerPort": 0},
    }
    assert observed() == expected
    assert all(
        set(point.attributes) == {"resource_class"}
        for points in measurements(metric_reader).values()
        for point in points
    )

    acquired.release()
    unavailable.data["avail"] = True
    del exporter.groups["extra"]["broken"]
    expected["labgrid_exporter_resources_configured"]["NetworkSerialPort"] = 4
    expected["labgrid_exporter_resources_free"]["NetworkSerialPort"] = 3
    expected["labgrid_exporter_resources_unavailable"]["NetworkSerialPort"] = 1
    expected["labgrid_exporter_resources_acquired"]["NetworkSerialPort"] = 1
    expected["labgrid_exporter_resources_broken"]["NetworkSerialPort"] = 0
    assert observed() == expected

    del exporter.groups["power"]
    assert all("NetworkPowerPort" not in classes for classes in observed().values())


def test_exporter_metrics_registration_once(metric_reader, monkeypatch):
    exporter = make_exporter()
    meter = otel_metrics.get_meter("labgrid.remote.exporter")
    create_gauge = Mock(wraps=meter.create_observable_gauge)
    create_counter = Mock(wraps=meter.create_counter)
    monkeypatch.setattr(meter, "create_observable_gauge", create_gauge)
    monkeypatch.setattr(meter, "create_counter", create_counter)
    setup_exporter_metrics(exporter)
    setup_exporter_metrics(exporter)
    assert create_gauge.call_count == 5
    create_counter.assert_called_once()


@pytest.mark.parametrize("operation", ["acquire", "release"])
@pytest.mark.parametrize(
    "error_type", [None, BrokenResourceError, InvalidResourceRequestError, UnknownResourceError, RuntimeError]
)
def test_resource_command_outcomes(metric_reader, operation, error_type):
    async def run():
        exporter = make_exporter()
        exporter.acquire = AsyncMock()
        exporter.release = AsyncMock()
        setup_exporter_metrics(exporter)
        if error_type:
            getattr(exporter, operation).side_effect = error_type("resource command failed")

        message = pb2.ExporterOutMessage()
        message.set_acquired_request.group_name = "group"
        message.set_acquired_request.resource_name = "resource"
        if operation == "acquire":
            message.set_acquired_request.place_name = "place"
        if error_type is RuntimeError:
            with pytest.raises(RuntimeError, match="resource command failed"):
                await exporter._handle_set_acquired_request(message)
        else:
            await exporter._handle_set_acquired_request(message)
        return exporter.out_queue.get_nowait().response

    response = asyncio.run(run())
    assert response.success is (error_type is None)
    points = measurements(metric_reader)["labgrid_exporter_resource_commands_total"]
    assert len(points) == 1
    assert points[0].value == 1
    assert points[0].attributes == {"operation": operation, "outcome": "failure" if error_type else "success"}


def test_disabled_exporter_does_not_use_another_instances_counter(metric_reader):
    enabled = make_exporter()
    disabled = make_exporter()
    setup_exporter_metrics(enabled)
    record_resource_command(enabled, "acquire", True)
    record_resource_command(disabled, "release", False)
    points = measurements(metric_reader)["labgrid_exporter_resource_commands_total"]
    assert len(points) == 1
    assert points[0].attributes == {"operation": "acquire", "outcome": "success"}
    assert points[0].value == 1


def test_metrics_disabled(monkeypatch):
    monkeypatch.setenv("OTEL_METRICS_EXPORTER", "none")
    assert not otel_metrics.setup_metrics(None)
    exporter = make_exporter()
    setup_exporter_metrics(exporter)
    record_resource_command(exporter, "acquire", True)
    assert not hasattr(exporter, "_otel_resource_commands")


def test_sdk_disabled(monkeypatch):
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    assert not otel_metrics.setup_metrics(None)
    exporter = make_exporter()
    setup_exporter_metrics(exporter)
    record_resource_command(exporter, "acquire", False)
    assert not hasattr(exporter, "_otel_resource_commands")
