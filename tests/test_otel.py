import queue
from time import monotonic, sleep

import grpc
import pytest
import requests

from labgrid.remote.generated import labgrid_coordinator_pb2, labgrid_coordinator_pb2_grpc
from labgrid.util import get_free_port

pytest.importorskip("opentelemetry.exporter.prometheus")
prometheus_parser = pytest.importorskip("prometheus_client.parser")


@pytest.fixture
def otel_env(monkeypatch):
    """Enable telemetry for otel tests"""
    monkeypatch.setenv("OTEL_SDK_DISABLED", "false")
    monkeypatch.setenv("OTEL_METRICS_EXPORTER", "prometheus")
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "none")


def test_parse_exporters():
    from labgrid.remote.otel import _parse_exporters

    supported = {"prometheus", "otlp"}

    assert _parse_exporters("", default=supported, supported=supported) == supported
    assert _parse_exporters(" Prometheus, OTLP ", default=set(), supported=supported) == supported
    assert _parse_exporters("none", default=supported, supported=supported) == set()

    with pytest.raises(RuntimeError, match="Unsupported OTel exporters"):
        _parse_exporters("prometheus,invalid", default=set(), supported=supported)
    with pytest.raises(RuntimeError, match="Unsupported OTel exporters"):
        _parse_exporters("none,otlp", default=set(), supported=supported)


@pytest.fixture(autouse=True)
def prometheus_endpoint(monkeypatch):
    host = "127.0.0.1"
    port = get_free_port()
    monkeypatch.setenv("OTEL_EXPORTER_PROMETHEUS_HOST", host)
    monkeypatch.setenv("OTEL_EXPORTER_PROMETHEUS_PORT", str(port))
    return f"http://{host}:{port}/metrics"


@pytest.fixture
def channel_stub():
    messages = queue.Queue()
    channel = grpc.insecure_channel("127.0.0.1:20408")
    stub = labgrid_coordinator_pb2_grpc.CoordinatorStub(channel)

    def client_messages():
        startup = labgrid_coordinator_pb2.ClientInMessage()
        startup.startup.version = "2.0.0"
        startup.startup.name = "testclient"
        yield startup
        while True:
            message = messages.get()
            yield message
            messages.task_done()

    _stream = stub.ClientStream(client_messages())
    yield stub
    channel.close()


def scrape_sample(endpoint, name):
    response = requests.get(endpoint, timeout=5)
    response.raise_for_status()

    for family in prometheus_parser.text_string_to_metric_families(response.text):
        for sample in family.samples:
            if sample.name == name:
                return sample

    pytest.fail(f"Prometheus sample {name!r} was not found")


def create_reservation(channel_stub, tags):
    response = channel_stub.CreateReservation(
        labgrid_coordinator_pb2.CreateReservationRequest(
            filters={"main": labgrid_coordinator_pb2.Reservation.Filter(filter=tags)},
            prio=1.0,
        )
    )
    return response.reservation.token


def test_coordinator_metrics(coordinator, channel_stub, prometheus_endpoint):
    target = scrape_sample(prometheus_endpoint, "target_info")
    assert target.labels["service_name"] == "labgrid-coordinator"

    registered_metric = "labgrid_coordinator_places_registered"
    acquired_metric = "labgrid_coordinator_places_acquired"
    available_metric = "labgrid_coordinator_places_available"
    waiting_metric = "labgrid_coordinator_reservations_waiting"
    wait_duration_metric = "labgrid_coordinator_reservation_wait_duration_seconds"
    allocated_metric = "labgrid_coordinator_reservations_allocated"
    exporters_metric = "labgrid_coordinator_exporters_connected"
    resources_metric = "labgrid_coordinator_resources_registered"

    metric = scrape_sample(prometheus_endpoint, registered_metric)
    assert metric.value == 0
    assert metric.labels["otel_scope_name"] == "labgrid.remote.coordinator"
    assert set(metric.labels) <= {"otel_scope_name", "otel_scope_version", "otel_scope_schema_url"}
    assert scrape_sample(prometheus_endpoint, acquired_metric).value == 0
    assert scrape_sample(prometheus_endpoint, available_metric).value == 0
    assert scrape_sample(prometheus_endpoint, waiting_metric).value == 0
    assert scrape_sample(prometheus_endpoint, allocated_metric).value == 0
    assert scrape_sample(prometheus_endpoint, exporters_metric).value == 0
    assert scrape_sample(prometheus_endpoint, resources_metric).value == 0

    request = labgrid_coordinator_pb2.CreatePlaceRequest(name="test")
    channel_stub.CreatePlace(request)
    assert scrape_sample(prometheus_endpoint, registered_metric).value == 1
    assert scrape_sample(prometheus_endpoint, available_metric).value == 1

    channel_stub.AcquirePlace(labgrid_coordinator_pb2.AcquirePlaceRequest(placename="test"))
    assert scrape_sample(prometheus_endpoint, acquired_metric).value == 1
    assert scrape_sample(prometheus_endpoint, available_metric).value == 0

    channel_stub.ReleasePlace(labgrid_coordinator_pb2.ReleasePlaceRequest(placename="test"))
    assert scrape_sample(prometheus_endpoint, acquired_metric).value == 0
    assert scrape_sample(prometheus_endpoint, available_metric).value == 1

    tags = {"board": "test"}
    channel_stub.SetPlaceTags(labgrid_coordinator_pb2.SetPlaceTagsRequest(placename="test", tags=tags))

    waiting_token = create_reservation(channel_stub, {"board": "missing"})
    assert scrape_sample(prometheus_endpoint, waiting_metric).value == 1
    assert scrape_sample(prometheus_endpoint, allocated_metric).value == 0

    allocated_token = create_reservation(channel_stub, tags)
    assert scrape_sample(prometheus_endpoint, waiting_metric).value == 1
    assert scrape_sample(prometheus_endpoint, allocated_metric).value == 1
    assert scrape_sample(prometheus_endpoint, f"{wait_duration_metric}_count").value == 1
    assert scrape_sample(prometheus_endpoint, f"{wait_duration_metric}_sum").value >= 0
    assert scrape_sample(prometheus_endpoint, available_metric).value == 0

    channel_stub.CancelReservation(labgrid_coordinator_pb2.CancelReservationRequest(token=allocated_token))
    assert scrape_sample(prometheus_endpoint, allocated_metric).value == 0
    assert scrape_sample(prometheus_endpoint, available_metric).value == 1

    channel_stub.CancelReservation(labgrid_coordinator_pb2.CancelReservationRequest(token=waiting_token))
    assert scrape_sample(prometheus_endpoint, waiting_metric).value == 0

    request = labgrid_coordinator_pb2.DeletePlaceRequest(name="test")
    channel_stub.DeletePlace(request)
    assert scrape_sample(prometheus_endpoint, registered_metric).value == 0
    assert scrape_sample(prometheus_endpoint, available_metric).value == 0


def test_coordinator_exporter_metrics(coordinator, exporter, prometheus_endpoint):
    with grpc.insecure_channel("127.0.0.1:20408") as channel:
        stub = labgrid_coordinator_pb2_grpc.CoordinatorStub(channel)
        deadline = monotonic() + 10
        request = labgrid_coordinator_pb2.ListResourcesRequest()
        resources = []
        while monotonic() < deadline:
            try:
                resources = stub.ListResources(request, timeout=1).resources
            except grpc.RpcError as error:
                if error.code() is not grpc.StatusCode.DEADLINE_EXCEEDED:
                    raise
                continue
            if len(resources) == 5:
                break
            sleep(0.1)

    assert len(resources) == 5
    assert scrape_sample(prometheus_endpoint, "labgrid_coordinator_exporters_connected").value == 1
    assert scrape_sample(prometheus_endpoint, "labgrid_coordinator_resources_registered").value == 5
