import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from opentelemetry import metrics, trace

from labgrid.remote import otel, otel_metrics
from labgrid.remote.common import Place, Reservation, ReservationState
from labgrid.remote.coordinator import Coordinator


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


@pytest.fixture
def coordinator_state():
    # Exercise scheduling without background polling or filesystem persistence.
    coordinator = object.__new__(Coordinator)
    coordinator.places = {}
    coordinator.reservations = {}
    coordinator.exporters = {}
    coordinator.clients = {}
    coordinator.lock = Mock()
    coordinator.lock.locked.return_value = True
    return coordinator


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


def test_coordinator_gauges(metric_reader, coordinator_state):
    coordinator = coordinator_state
    otel_metrics.setup_coordinator_metrics(coordinator)
    expected = {
        "labgrid_coordinator_places_registered": 0,
        "labgrid_coordinator_places_acquired": 0,
        "labgrid_coordinator_places_available": 0,
        "labgrid_coordinator_reservations_waiting": 0,
        "labgrid_coordinator_reservations_allocated": 0,
        "labgrid_coordinator_exporters_connected": 0,
        "labgrid_coordinator_resources_registered": 0,
    }
    assert {name: points[0].value for name, points in measurements(metric_reader).items()} == expected

    available = Place(name="available")
    acquired = Place(name="acquired", acquired="client")
    reserved = Place(name="reserved", reservation="allocated")
    coordinator.places.update({place.name: place for place in [available, acquired, reserved]})
    waiting = Reservation(owner="waiting")
    allocated = Reservation(owner="allocated", state="allocated", allocations={"main": [reserved.name]})
    coordinator.reservations.update({reservation.token: reservation for reservation in [waiting, allocated]})
    coordinator.exporters["first"] = SimpleNamespace(groups={"one": {"a": object(), "b": object()}})
    coordinator.exporters["second"] = SimpleNamespace(groups={"two": {"c": object()}, "empty": {}})
    expected.update(
        labgrid_coordinator_places_registered=3,
        labgrid_coordinator_places_acquired=1,
        labgrid_coordinator_places_available=1,
        labgrid_coordinator_reservations_waiting=1,
        labgrid_coordinator_reservations_allocated=1,
        labgrid_coordinator_exporters_connected=2,
        labgrid_coordinator_resources_registered=3,
    )
    observed = measurements(metric_reader)
    assert {name: points[0].value for name, points in observed.items()} == expected
    assert all(not point.attributes for points in observed.values() for point in points)

    # Callbacks must reflect removals and transitions, not registration-time state.
    acquired.acquired = None
    coordinator.reservations.clear()
    reserved.reservation = None
    coordinator.exporters.clear()
    expected.update(
        labgrid_coordinator_places_acquired=0,
        labgrid_coordinator_places_available=3,
        labgrid_coordinator_reservations_waiting=0,
        labgrid_coordinator_reservations_allocated=0,
        labgrid_coordinator_exporters_connected=0,
        labgrid_coordinator_resources_registered=0,
    )
    assert {name: points[0].value for name, points in measurements(metric_reader).items()} == expected


def test_first_reservation_allocation(metric_reader, coordinator_state, monkeypatch):
    coordinator = coordinator_state
    otel_metrics.setup_coordinator_metrics(coordinator)
    reservation = Reservation(owner="client", filters={"main": {"board": "test"}}, created=1000.0)
    coordinator.reservations[reservation.token] = reservation
    monkeypatch.setattr("labgrid.remote.coordinator.time.time", lambda: 1007.5)
    coordinator.schedule_reservations()
    name = "labgrid_coordinator_reservation_wait_duration_seconds"
    assert name not in measurements(metric_reader)

    place = Place(name="test", tags={"board": "test"})
    coordinator.places[place.name] = place
    coordinator.schedule_reservations()
    assert reservation.state is ReservationState.allocated
    histogram = measurements(metric_reader)[name][0]
    assert histogram.count == 1
    assert histogram.sum == 7.5

    # Polling and acquired -> allocated transitions are not new observations.
    coordinator.schedule_reservations()
    place.acquired = "client"
    coordinator.schedule_reservations()
    assert reservation.state is ReservationState.acquired
    place.acquired = None
    coordinator.schedule_reservations()
    assert reservation.state is ReservationState.allocated
    assert measurements(metric_reader)[name][0].count == 1

    # Defend against future scheduler changes which requeue an existing reservation.
    reservation.allocations.clear()
    reservation.state = ReservationState.waiting
    place.reservation = None
    coordinator.schedule_reservations()
    assert measurements(metric_reader)[name][0].count == 1


def test_reservation_wait_duration_clamps_clock_changes(metric_reader, coordinator_state):
    otel_metrics.setup_coordinator_metrics(coordinator_state)
    reservation = Reservation(owner="client")
    otel_metrics.record_reservation_wait_duration(coordinator_state, reservation, -1.0)
    histogram = measurements(metric_reader)["labgrid_coordinator_reservation_wait_duration_seconds"][0]
    assert histogram.count == 1
    assert histogram.sum == 0


def test_metric_registration_is_idempotent(metric_reader, coordinator_state, monkeypatch):
    meter = otel_metrics.get_meter("labgrid.remote.coordinator")
    create_gauge = Mock(wraps=meter.create_observable_gauge)
    monkeypatch.setattr(meter, "create_observable_gauge", create_gauge)
    otel_metrics.setup_coordinator_metrics(coordinator_state)
    otel_metrics.setup_coordinator_metrics(coordinator_state)
    assert create_gauge.call_count == 7
    assert len(measurements(metric_reader)) == 7


@pytest.mark.parametrize("setting", ["true", " TRUE "])
def test_sdk_disabled(monkeypatch, coordinator_state, setting):
    monkeypatch.setenv("OTEL_SDK_DISABLED", setting)
    assert not otel_metrics.setup_metrics(None)
    otel_metrics.setup_coordinator_metrics(coordinator_state)
    otel_metrics.record_reservation_wait_duration(coordinator_state, Reservation(owner="client"), 1)
    assert not hasattr(coordinator_state, "_otel_reservation_wait_duration")


def test_sdk_absent(monkeypatch, coordinator_state):
    monkeypatch.setitem(sys.modules, "opentelemetry.sdk.metrics", None)
    assert not otel_metrics.setup_metrics(None)
    otel_metrics.setup_coordinator_metrics(coordinator_state)
    assert not hasattr(coordinator_state, "_otel_reservation_wait_duration")


def test_metrics_disabled(monkeypatch, coordinator_state):
    monkeypatch.setenv("OTEL_METRICS_EXPORTER", "none")
    assert not otel_metrics.setup_metrics(None)
    assert otel_metrics.get_meter("test") is None
    otel_metrics.setup_coordinator_metrics(coordinator_state)
    assert not hasattr(coordinator_state, "_otel_reservation_wait_duration")


@pytest.mark.parametrize("setting", ["invalid", "none,otlp", "prometheus,", "console"])
def test_invalid_exporter(setting, monkeypatch):
    monkeypatch.setenv("OTEL_METRICS_EXPORTER", setting)
    with pytest.raises(ValueError, match="Unsupported OpenTelemetry exporters"):
        otel_metrics.setup_metrics(None)


@pytest.fixture
def bootstrap(monkeypatch):
    sdk = pytest.importorskip("opentelemetry.sdk.metrics")
    export = pytest.importorskip("opentelemetry.sdk.metrics.export")
    prometheus = pytest.importorskip("opentelemetry.exporter.prometheus")
    otlp = pytest.importorskip("opentelemetry.exporter.otlp.proto.grpc.metric_exporter")
    prometheus_client = pytest.importorskip("prometheus_client")
    resource = pytest.importorskip("opentelemetry.sdk.resources").Resource.create({"service.name": "test"})
    state = SimpleNamespace(provider=object(), readers=[], exported=[], resource=resource)

    def reader(name):
        result = export.InMemoryMetricReader()
        state.readers.append((name, result))
        return result

    def set_provider(provider):
        state.provider = provider

    state.http_server = Mock()
    state.otlp_exporter = Mock()
    monkeypatch.setattr(prometheus, "PrometheusMetricReader", lambda: reader("prometheus"))
    monkeypatch.setattr(prometheus_client, "start_http_server", state.http_server)
    monkeypatch.setattr(otlp, "OTLPMetricExporter", state.otlp_exporter)
    monkeypatch.setattr(export, "PeriodicExportingMetricReader", lambda _exporter: reader("otlp"))
    monkeypatch.setattr(metrics, "get_meter_provider", lambda: state.provider)
    monkeypatch.setattr(metrics, "set_meter_provider", set_provider)
    yield state
    if isinstance(state.provider, sdk.MeterProvider):
        state.provider.shutdown()


@pytest.mark.parametrize(
    ("setting", "expected"),
    [("", {"prometheus"}), ("otlp", {"otlp"}), (" Prometheus, OTLP ", {"prometheus", "otlp"})],
)
def test_exporter_selection(bootstrap, monkeypatch, setting, expected):
    monkeypatch.setenv("OTEL_METRICS_EXPORTER", setting)
    monkeypatch.setenv("OTEL_EXPORTER_PROMETHEUS_HOST", "127.0.0.1")
    monkeypatch.setenv("OTEL_EXPORTER_PROMETHEUS_PORT", "9465")
    assert otel_metrics.setup_metrics(bootstrap.resource)
    assert {name for name, _reader in bootstrap.readers} == expected
    assert bootstrap.otlp_exporter.call_count == int("otlp" in expected)
    if "prometheus" in expected:
        bootstrap.http_server.assert_called_once_with(addr="127.0.0.1", port=9465)
    else:
        bootstrap.http_server.assert_not_called()

    # Repeated setup reuses the installed provider and does not start another server.
    provider = bootstrap.provider
    assert otel_metrics.setup_metrics(bootstrap.resource)
    assert bootstrap.provider is provider
    assert len(bootstrap.readers) == len(expected)
    assert bootstrap.http_server.call_count == int("prometheus" in expected)


def test_reuse_preconfigured_provider(metric_reader, monkeypatch):
    set_provider = Mock()
    monkeypatch.setattr(metrics, "set_meter_provider", set_provider)
    assert otel_metrics.setup_metrics(None)
    set_provider.assert_not_called()
    counter = otel_metrics.get_meter("test").create_counter("test_preconfigured")
    counter.add(3)
    assert measurements(metric_reader)["test_preconfigured"][0].value == 3


def test_shared_bootstrap_metrics_without_traces(bootstrap, monkeypatch):
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "none")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "custom-coordinator")
    monkeypatch.setattr(trace, "get_tracer_provider", trace.ProxyTracerProvider)
    monkeypatch.setattr(otel, "_enabled", False)
    set_tracer = Mock()
    monkeypatch.setattr(trace, "set_tracer_provider", set_tracer)
    assert otel.setup_otel("labgrid-coordinator", with_metrics=True)
    otel_metrics.get_meter("test").create_counter("bootstrap_test").add(1)
    data = bootstrap.readers[0][1].get_metrics_data()
    assert data.resource_metrics[0].resource.attributes["service.name"] == "custom-coordinator"
    assert [name for name, _reader in bootstrap.readers] == ["prometheus"]
    set_tracer.assert_not_called()
