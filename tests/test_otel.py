import asyncio
import importlib
import queue
from time import sleep, time
from types import SimpleNamespace

import grpc
import pytest
import pytest_asyncio
import requests
from grpc_health.v1 import health_pb2, health_pb2_grpc

from labgrid.remote.coordinator import Coordinator
from labgrid.remote.grpc.health import HealthServicer
from labgrid.remote.generated import labgrid_coordinator_pb2, labgrid_coordinator_pb2_grpc
from labgrid.util import get_free_port

pytest.importorskip("opentelemetry.exporter.prometheus")
prometheus_parser = pytest.importorskip("prometheus_client.parser")


@pytest_asyncio.fixture
async def instrumented_health_server():
    from opentelemetry.instrumentation.grpc import aio_server_interceptor
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    server = grpc.aio.server(interceptors=[aio_server_interceptor(tracer_provider=provider)])
    servicer = HealthServicer()
    for name in ("", "labgrid.Coordinator"):
        await servicer.set(name, health_pb2.HealthCheckResponse.SERVING)
    health_pb2_grpc.add_HealthServicer_to_server(servicer, server)
    coordinator = Coordinator.__new__(Coordinator)
    coordinator.use_capabilities = False
    coordinator.lock = asyncio.Lock()
    coordinator.places = {}
    labgrid_coordinator_pb2_grpc.add_CoordinatorServicer_to_server(coordinator, server)
    port = server.add_insecure_port("127.0.0.1:0")
    try:
        await server.start()
        async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            yield SimpleNamespace(
                server=server,
                servicer=servicer,
                health=health_pb2_grpc.HealthStub(channel),
                coordinator=labgrid_coordinator_pb2_grpc.CoordinatorStub(channel),
                exporter=exporter,
            )
    finally:
        await server.stop(0)
        provider.shutdown()


async def wait_for_rpc_spans(exporter, *methods):
    # The client can observe termination before the interceptor exports its span.
    async def wait():
        while not set(methods) <= {span.attributes.get("rpc.method") for span in exporter.get_finished_spans()}:
            await asyncio.sleep(0.01)

    await asyncio.wait_for(wait(), timeout=2)


@pytest.mark.asyncio
async def test_health_and_coordinator_rpcs_with_grpc_instrumentation(instrumented_health_server):
    service = instrumented_health_server
    response = await service.health.Check(health_pb2.HealthCheckRequest(), timeout=2)
    assert response.status == health_pb2.HealthCheckResponse.SERVING
    places = await service.coordinator.GetPlaces(labgrid_coordinator_pb2.GetPlacesRequest(), timeout=2)
    assert not places.places
    await wait_for_rpc_spans(service.exporter, "Check", "GetPlaces")


@pytest.mark.asyncio
@pytest.mark.parametrize("service_name", ["", "labgrid.Coordinator", "missing"])
async def test_health_watch_with_grpc_instrumentation(instrumented_health_server, service_name):
    service = instrumented_health_server
    stream = service.health.Watch(health_pb2.HealthCheckRequest(service=service_name), timeout=5)
    expected = (
        health_pb2.HealthCheckResponse.SERVICE_UNKNOWN
        if service_name == "missing"
        else health_pb2.HealthCheckResponse.SERVING
    )
    assert (await stream.read()).status == expected
    if service_name == "missing":
        await service.servicer.set(service_name, health_pb2.HealthCheckResponse.SERVING)
        assert (await stream.read()).status == health_pb2.HealthCheckResponse.SERVING
    await service.servicer.enter_graceful_shutdown()
    assert (await stream.read()).status == health_pb2.HealthCheckResponse.NOT_SERVING
    stopping = asyncio.create_task(service.server.stop(0.2))
    try:
        with pytest.raises(grpc.aio.AioRpcError) as excinfo:
            await stream.read()
        assert excinfo.value.code() == grpc.StatusCode.UNAVAILABLE
    finally:
        await stopping
    await wait_for_rpc_spans(service.exporter, "Watch")


@pytest.mark.asyncio
@pytest.mark.parametrize("service_name", ["", "labgrid.Coordinator", "missing"])
@pytest.mark.parametrize("termination", ["cancel", "deadline"])
async def test_health_watch_termination_with_grpc_instrumentation(
    instrumented_health_server, service_name, termination
):
    service = instrumented_health_server
    stream = service.health.Watch(
        health_pb2.HealthCheckRequest(service=service_name), timeout=0.5 if termination == "deadline" else 5
    )
    # Establish the stream before cancelling it or waiting for its deadline.
    await stream.read()
    if termination == "cancel":
        stream.cancel()
        with pytest.raises(asyncio.CancelledError):
            await stream.read()
    else:
        with pytest.raises(grpc.aio.AioRpcError) as excinfo:
            await stream.read()
        assert excinfo.value.code() == grpc.StatusCode.DEADLINE_EXCEEDED
    await wait_for_rpc_spans(service.exporter, "Watch")


@pytest.fixture
def otel_env(monkeypatch):
    """Enable telemetry for otel tests"""
    monkeypatch.setenv("OTEL_SDK_DISABLED", "false")
    monkeypatch.setenv("OTEL_METRICS_EXPORTER", "prometheus")
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "none")


@pytest.mark.parametrize("module_name", ["labgrid.remote.otel", "labgrid.remote.otel_exporter"])
def test_parse_exporters(module_name):
    parse_exporters = importlib.import_module(module_name)._parse_exporters
    supported = {"prometheus", "otlp"}

    assert parse_exporters("", default=supported, supported=supported) == supported
    assert parse_exporters(" Prometheus, OTLP ", default=set(), supported=supported) == supported
    assert parse_exporters("none", default=supported, supported=supported) == set()

    with pytest.raises(RuntimeError, match="Unsupported OTel exporters"):
        parse_exporters("prometheus,invalid", default=set(), supported=supported)
    with pytest.raises(RuntimeError, match="Unsupported OTel exporters"):
        parse_exporters("none,otlp", default=set(), supported=supported)


@pytest.fixture(autouse=True)
def prometheus_endpoint(monkeypatch):
    host = "127.0.0.1"
    port = get_free_port()
    monkeypatch.setenv("OTEL_EXPORTER_PROMETHEUS_HOST", host)
    monkeypatch.setenv("OTEL_EXPORTER_PROMETHEUS_PORT", str(port))
    return f"http://{host}:{port}/metrics"


@pytest.fixture
def exporter_metrics_endpoint(coordinator, monkeypatch, request):
    """Start the shared exporter with a metrics port separate from the coordinator."""
    host = "127.0.0.1"
    port = get_free_port()
    monkeypatch.setenv("OTEL_EXPORTER_PROMETHEUS_HOST", host)
    monkeypatch.setenv("OTEL_EXPORTER_PROMETHEUS_PORT", str(port))

    # Start the exporter after changing the environment inherited by its subprocess.
    request.getfixturevalue("exporter")
    return f"http://{host}:{port}/metrics"


@pytest.fixture
def channel_stub(coordinator):
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


def scrape_samples(endpoint, name):
    response = requests.get(endpoint, timeout=5)
    response.raise_for_status()
    samples = []
    for family in prometheus_parser.text_string_to_metric_families(response.text):
        for sample in family.samples:
            if sample.name == name:
                samples.append(sample)
    return samples


def scrape_sample(endpoint, name, operation=None):
    for sample in scrape_samples(endpoint, name):
        if operation is None or sample.labels.get("operation") == operation:
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


def test_coordinator_lease_max_duration_remaining_lifecycle(coordinator, channel_stub, prometheus_endpoint):
    metric_name = "labgrid_coordinator_lease_max_duration_remaining_seconds"
    max_lease_duration = 20
    place_names = ("lease-one", "lease-two")
    tokens = {}

    for place_name in place_names:
        channel_stub.CreatePlace(labgrid_coordinator_pb2.CreatePlaceRequest(name=place_name))
        channel_stub.SetPlaceTags(
            labgrid_coordinator_pb2.SetPlaceTagsRequest(
                placename=place_name,
                tags={"board": place_name},
            )
        )
        tokens[place_name] = create_reservation(channel_stub, {"board": place_name})

    assert scrape_samples(prometheus_endpoint, metric_name) == []

    reservations = {}
    for place_name in place_names:
        channel_stub.LeasePlace(labgrid_coordinator_pb2.LeasePlaceRequest(placename=place_name))
        reservations[place_name] = channel_stub.PollReservation(
            labgrid_coordinator_pb2.PollReservationRequest(token=tokens[place_name])
        ).reservation

    initial_scrape_started = time()
    initial_samples = scrape_samples(prometheus_endpoint, metric_name)
    initial_scrape_finished = time()
    assert len(initial_samples) == len(place_names)
    assert {sample.labels["place_name"] for sample in initial_samples} == set(place_names)
    initial_by_place = {sample.labels["place_name"]: sample for sample in initial_samples}

    def lease_start(reservation):
        return reservation.lease_start_time.seconds + reservation.lease_start_time.nanos / 1e9

    clock_tolerance = 0.02
    for place_name, reservation in reservations.items():
        deadline = lease_start(reservation) + max_lease_duration
        earliest_remaining = max(0, deadline - initial_scrape_finished)
        latest_remaining = max(0, deadline - initial_scrape_started)
        assert earliest_remaining - clock_tolerance <= initial_by_place[place_name].value
        assert initial_by_place[place_name].value <= latest_remaining + clock_tolerance

    initial_countdown = initial_by_place["lease-one"].value
    initial_deadline = lease_start(reservations["lease-one"]) + max_lease_duration
    initial_earliest_remaining = max(0, initial_deadline - initial_scrape_finished)
    extension_capacity = initial_deadline - reservations["lease-one"].timeout
    assert extension_capacity < initial_earliest_remaining - clock_tolerance

    sleep(0.6)
    later_samples = scrape_samples(prometheus_endpoint, metric_name)
    later_by_place = {sample.labels["place_name"]: sample for sample in later_samples}
    assert later_by_place["lease-one"].value < initial_countdown - 0.3

    extended = channel_stub.ExtendLease(
        labgrid_coordinator_pb2.ExtendLeaseRequest(token=tokens["lease-one"])
    ).reservation
    assert extended.timeout > reservations["lease-one"].timeout

    extended_scrape_started = time()
    extended_samples = scrape_samples(prometheus_endpoint, metric_name)
    extended_scrape_finished = time()
    extended_by_place = {sample.labels["place_name"]: sample for sample in extended_samples}
    extended_countdown = extended_by_place["lease-one"].value
    assert extended_countdown <= later_by_place["lease-one"].value
    extended_deadline = lease_start(extended) + max_lease_duration
    earliest_remaining = max(0, extended_deadline - extended_scrape_finished)
    latest_remaining = max(0, extended_deadline - extended_scrape_started)
    assert earliest_remaining - clock_tolerance <= extended_countdown
    assert extended_countdown <= latest_remaining + clock_tolerance
    extension_capacity = extended_deadline - extended.timeout
    assert extension_capacity < earliest_remaining - clock_tolerance

    channel_stub.ReleasePlace(labgrid_coordinator_pb2.ReleasePlaceRequest(placename="lease-one"))
    remaining_samples = scrape_samples(prometheus_endpoint, metric_name)
    assert len(remaining_samples) == 1
    assert remaining_samples[0].labels["place_name"] == "lease-two"

    channel_stub.ReleasePlace(labgrid_coordinator_pb2.ReleasePlaceRequest(placename="lease-two"))
    assert scrape_samples(prometheus_endpoint, metric_name) == []


def test_coordinator_exporter_metrics(exporter_metrics_endpoint, prometheus_endpoint):
    for _ in range(100):
        resources = scrape_sample(
            prometheus_endpoint,
            "labgrid_coordinator_resources_registered",
        )
        if resources.value == 5:
            break
        sleep(0.1)

    assert resources.value == 5
    assert scrape_sample(prometheus_endpoint, "labgrid_coordinator_exporters_connected").value == 1


def test_exporter_metrics(exporter_metrics_endpoint):
    target = scrape_sample(exporter_metrics_endpoint, "target_info")
    assert target.labels["service_name"] == "labgrid-exporter"

    for name in (
        "labgrid_exporter_resources_configured",
        "labgrid_exporter_resources_free",
        "labgrid_exporter_resources_unavailable",
        "labgrid_exporter_resources_acquired",
        "labgrid_exporter_resources_broken",
    ):
        metric = scrape_sample(exporter_metrics_endpoint, name)
        assert metric.labels["otel_scope_name"] == "labgrid.remote.exporter"
        assert metric.labels["resource_class"]


def test_exporter_resource_command_metrics(exporter_metrics_endpoint, channel_stub):
    command_metric = "labgrid_exporter_resource_commands_total"

    channel_stub.CreatePlace(labgrid_coordinator_pb2.CreatePlaceRequest(name="test"))
    channel_stub.AddPlaceMatch(labgrid_coordinator_pb2.AddPlaceMatchRequest(placename="test", pattern="*/Testport/*"))

    channel_stub.AcquirePlace(labgrid_coordinator_pb2.AcquirePlaceRequest(placename="test"))
    metric = scrape_sample(exporter_metrics_endpoint, command_metric, "acquire")
    assert metric.labels["outcome"] == "success"
    assert metric.value == 1

    channel_stub.ReleasePlace(labgrid_coordinator_pb2.ReleasePlaceRequest(placename="test"))
    metric = scrape_sample(exporter_metrics_endpoint, command_metric, "release")
    assert metric.labels["outcome"] == "success"
    assert metric.value == 1

    tags = {"board": "test"}
    channel_stub.SetPlaceTags(labgrid_coordinator_pb2.SetPlaceTagsRequest(placename="test", tags=tags))
    token = create_reservation(channel_stub, tags)
    channel_stub.LeasePlace(labgrid_coordinator_pb2.LeasePlaceRequest(placename="test"))
    metric = scrape_sample(exporter_metrics_endpoint, command_metric, "lease_start")
    assert metric.labels["outcome"] == "success"
    assert metric.value == 1

    channel_stub.ExtendLease(labgrid_coordinator_pb2.ExtendLeaseRequest(token=token))
    metric = scrape_sample(exporter_metrics_endpoint, command_metric, "lease_extend")
    assert metric.labels["outcome"] == "success"
    assert metric.value == 1
