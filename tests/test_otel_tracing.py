import asyncio
import builtins
import inspect
import os
from types import SimpleNamespace

import grpc
import pytest
import pytest_asyncio
from grpc_health.v1 import health_pb2, health_pb2_grpc
from opentelemetry import trace

from labgrid.remote import otel
from labgrid.remote.coordinator import Coordinator
from labgrid.remote.generated import labgrid_coordinator_pb2 as pb2
from labgrid.remote.generated import labgrid_coordinator_pb2_grpc as pb2_grpc
from labgrid.remote.grpc.health import HealthServicer

sdk_trace = pytest.importorskip("opentelemetry.sdk.trace")
sdk_export = pytest.importorskip("opentelemetry.sdk.trace.export")
memory_export = pytest.importorskip("opentelemetry.sdk.trace.export.in_memory_span_exporter")
grpc_instrumentation = pytest.importorskip("opentelemetry.instrumentation.grpc")


@pytest.fixture
def otel_state(monkeypatch):
    """Keep providers, instrumentation and environment changes local to each test."""
    for name in os.environ:
        if name.startswith("OTEL_"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "none")
    monkeypatch.setattr(otel, "_enabled", False)

    providers = [trace.ProxyTracerProvider()]
    monkeypatch.setattr(trace, "get_tracer_provider", lambda: providers[-1])
    monkeypatch.setattr(trace, "set_tracer_provider", providers.append)
    instrumentor = grpc_instrumentation.GrpcAioInstrumentorServer()
    already_instrumented = instrumentor.is_instrumented_by_opentelemetry
    yield providers
    if not already_instrumented and instrumentor.is_instrumented_by_opentelemetry:
        instrumentor.uninstrument()
    for provider in providers:
        if isinstance(provider, sdk_trace.TracerProvider):
            provider.shutdown()


@pytest.fixture
def exported_spans(otel_state):
    exporter = memory_export.InMemorySpanExporter()
    provider = sdk_trace.TracerProvider(shutdown_on_exit=False)
    provider.add_span_processor(sdk_export.SimpleSpanProcessor(exporter))
    otel_state.append(provider)
    return exporter


@pytest.mark.parametrize("value, expected", [("", {"otlp"}), (" OTLP ", {"otlp"}), ("none", set())])
def test_parse_exporters(value, expected):
    assert otel._parse_exporters(value, default={"otlp"}, supported={"otlp"}) == expected


@pytest.mark.parametrize("value", ["unknown", "none,otlp", "otlp,"])
def test_invalid_exporters(value):
    with pytest.raises(ValueError, match="Unsupported OpenTelemetry exporters"):
        otel._parse_exporters(value, default={"otlp"}, supported={"otlp"})


def test_sdk_disabled(otel_state, monkeypatch):
    monkeypatch.setenv("OTEL_SDK_DISABLED", " TRUE ")
    assert not otel.setup_otel("labgrid-coordinator")
    assert not otel.instrument_grpc_server()
    assert len(otel_state) == 1


def test_sdk_not_installed(otel_state, monkeypatch):
    original_import = builtins.__import__

    def without_sdk(name, *args, **kwargs):
        if name.startswith("opentelemetry.sdk"):
            raise ModuleNotFoundError(name=name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_sdk)
    assert not otel.setup_otel("labgrid-coordinator")
    assert not otel.instrument_grpc_server()
    assert len(otel_state) == 1


def test_exporter_none_does_not_create_provider(otel_state):
    assert otel.setup_otel("labgrid-coordinator")
    assert len(otel_state) == 1


@pytest.mark.parametrize("missing", ["opentelemetry.exporter.otlp", "opentelemetry.instrumentation.grpc"])
def test_partial_optional_dependencies(otel_state, monkeypatch, missing):
    original_import = builtins.__import__

    def without_optional_dependency(name, *args, **kwargs):
        if name.startswith(missing):
            raise ModuleNotFoundError(name=name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_optional_dependency)
    if missing == "opentelemetry.exporter.otlp":
        monkeypatch.setenv("OTEL_TRACES_EXPORTER", "otlp")
        assert not otel.setup_otel("labgrid-coordinator")
    else:
        assert otel.setup_otel("labgrid-coordinator")
        assert not otel.instrument_grpc_server()
    assert len(otel_state) == 1


def test_existing_provider_reused(otel_state, exported_spans):
    provider = trace.get_tracer_provider()
    assert otel.setup_otel("labgrid-coordinator")
    assert otel.setup_otel("labgrid-coordinator")
    assert trace.get_tracer_provider() is provider
    assert len(otel_state) == 2
    with trace.get_tracer(__name__).start_as_current_span("existing-provider"):
        pass
    assert [span.name for span in exported_spans.get_finished_spans()] == ["existing-provider"]


def test_otlp_setup(otel_state, monkeypatch):
    from opentelemetry.exporter.otlp.proto.grpc import trace_exporter

    exporter = memory_export.InMemorySpanExporter()
    constructor_calls = []

    def create_exporter(*args, **kwargs):
        constructor_calls.append((args, kwargs))
        return exporter

    monkeypatch.setattr(trace_exporter, "OTLPSpanExporter", create_exporter)
    monkeypatch.delenv("OTEL_TRACES_EXPORTER")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "custom-coordinator")
    assert otel.setup_otel("labgrid-coordinator")
    provider = trace.get_tracer_provider()
    assert provider.resource.attributes["service.name"] == "custom-coordinator"
    # Let the exporter resolve its SDK defaults and OTEL_EXPORTER_OTLP_* settings.
    assert constructor_calls == [((), {})]
    with trace.get_tracer(__name__).start_as_current_span("configured-provider"):
        pass
    assert provider.force_flush()
    assert [span.name for span in exporter.get_finished_spans()] == ["configured-provider"]
    assert otel.setup_otel("labgrid-coordinator")
    assert len(constructor_calls) == 1


def test_rpc_metadata(exported_spans):
    @otel.instrument_rpc({"priority": "prio", "tags": "tags", "missing": "missing"})
    async def rpc(self, request, context):
        return request.prio

    request = SimpleNamespace(prio=0.0, tags={"board": "test"})
    assert list(inspect.signature(rpc).parameters) == ["self", "request", "context"]
    with trace.get_tracer(__name__).start_as_current_span("rpc"):
        assert asyncio.run(rpc(None, request, None)) == 0.0
    attributes = exported_spans.get_finished_spans()[0].attributes
    assert attributes == {"priority": 0.0, "tags": "{'board': 'test'}"}


def test_coordinator_grpc_spans(exported_spans, monkeypatch, tmp_path):
    """Exercise real gRPC instrumentation, request metadata and an RPC error."""
    monkeypatch.chdir(tmp_path)
    assert otel.setup_otel("labgrid-coordinator")
    assert otel.instrument_grpc_server()
    assert otel.instrument_grpc_server()

    async def run():
        coordinator = Coordinator()
        server = grpc.aio.server()
        pb2_grpc.add_CoordinatorServicer_to_server(coordinator, server)
        port = server.add_insecure_port("127.0.0.1:0")
        await server.start()
        try:
            async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
                stub = pb2_grpc.CoordinatorStub(channel)
                parent_id = "0123456789abcdef0123456789abcdef"
                metadata = (("traceparent", f"00-{parent_id}-0123456789abcdef-01"),)
                await stub.AddPlace(pb2.AddPlaceRequest(name="test-board"), metadata=metadata)
                with pytest.raises(grpc.aio.AioRpcError) as error:
                    await stub.AddPlace(pb2.AddPlaceRequest(name="test-board"))
                assert error.value.code() == grpc.StatusCode.ALREADY_EXISTS
        finally:
            await server.stop(None)
            for task in coordinator.poll_tasks:
                task.cancel()
            await asyncio.gather(*coordinator.poll_tasks, return_exceptions=True)

    asyncio.run(run())
    spans = exported_spans.get_finished_spans()
    assert len(spans) == 2
    assert all(span.name == "/labgrid.Coordinator/AddPlace" for span in spans)
    assert all(span.kind == trace.SpanKind.SERVER for span in spans)
    assert all(span.attributes["labgrid.place.name"] == "test-board" for span in spans)
    assert spans[0].context.trace_id == int("0123456789abcdef0123456789abcdef", 16)
    assert spans[0].parent.span_id == int("0123456789abcdef", 16)
    assert spans[1].attributes["rpc.grpc.status_code"] == grpc.StatusCode.ALREADY_EXISTS.value[0]


@pytest_asyncio.fixture
async def instrumented_health_server(exported_spans):
    server = grpc.aio.server(
        interceptors=[grpc_instrumentation.aio_server_interceptor(tracer_provider=trace.get_tracer_provider())]
    )
    servicer = HealthServicer()
    for name in ("", "labgrid.Coordinator"):
        await servicer.set(name, health_pb2.HealthCheckResponse.SERVING)
    health_pb2_grpc.add_HealthServicer_to_server(servicer, server)
    coordinator = Coordinator.__new__(Coordinator)
    coordinator.lock = asyncio.Lock()
    coordinator.places = {}
    pb2_grpc.add_CoordinatorServicer_to_server(coordinator, server)
    port = server.add_insecure_port("127.0.0.1:0")
    try:
        await server.start()
        async with grpc.aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            yield SimpleNamespace(
                server=server,
                servicer=servicer,
                health=health_pb2_grpc.HealthStub(channel),
                coordinator=pb2_grpc.CoordinatorStub(channel),
                exporter=exported_spans,
            )
    finally:
        await server.stop(0)


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
    places = await service.coordinator.GetPlaces(pb2.GetPlacesRequest(), timeout=2)
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
