import logging
from functools import wraps
from os import environ

from opentelemetry import context, metrics, propagate, trace
from opentelemetry.metrics import Observation

OTEL_SDK_INSTALLED = False

LOGGER = logging.getLogger("otel")


def _parse_exporters(value, *, default, supported):
    """
    Parse and validate an OpenTelemetry exporter setting.

    Optional Values:  ``prometheus``, ``otlp``, or ``none``.
    The supplied default is used when the setting is empty.
    """
    if not value.strip():
        return default

    selected = {item.strip().lower() for item in value.split(",")}
    if selected == {"none"}:
        return set()

    unknown = selected - supported
    if unknown or "none" in selected:
        raise RuntimeError(f"Unsupported OTel exporters: {sorted(unknown or selected)}")

    return selected


def _monkeypatch_ExporterCommand_init(exportercommand):
    old_init = exportercommand.__init__

    def new_init(self, *k, **kw):
        old_init(self, *k, **kw)
        self._otel_context = context.get_current()

    exportercommand.__init__ = new_init


def instrument_rpc(old_rpc, metadata):
    @wraps(old_rpc)
    async def wrapper(self, request, *args, **kwargs):
        span = trace.get_current_span()

        for target, attribute in metadata.items():
            val = getattr(request, attribute, None)
            if val:
                val = str(val)
            span.set_attribute(target, val)

        return await old_rpc(self, request, *args, **kwargs)

    return wrapper


def _monkeypatch_add_rpc_metadata(coordinator):
    """
    Monkeypatch each RPC handler to add request parameters as attributes to the OTEL span.

    For example: `{"AddPlace": {"labgrid.place.name": "name"}`
    adds `request.name` as the `labgrid.place.name` attribute on the span.
    """
    attributes = {
        # "ClientStream": {},
        # "ExporterStream": {},
        "AddPlace": {"labgrid.place.name": "name"},
        "CreatePlace": {"labgrid.place.name": "name"},
        "DeletePlace": {"labgrid.place.name": "name"},
        "GetPlace": {"labgrid.place.name": "name"},
        # "GetPlaces": {},
        "ListPlaces": {
            "labgrid.request.filter": "filter",
            "labgrid.request.page_size": "page_size",
            "labgrid.request.page_token": "page_token",
        },
        "ListResources": {
            "labgrid.request.filter": "filter",
            "labgrid.request.page_size": "page_size",
            "labgrid.request.page_token": "page_token",
        },
        "ListPlaceResources": {"labgrid.place.name": "name"},
        "AddPlaceAlias": {"labgrid.place.name": "placename", "labgrid.place.alias": "alias"},
        "DeletePlaceAlias": {"labgrid.place.name": "placename", "labgrid.place.alias": "alias"},
        "SetPlaceTags": {"labgrid.place.name": "placename", "labgrid.place.tags": "tags"},
        "SetPlaceComment": {"labgrid.place.name": "placename", "labgrid.place.comment": "comment"},
        "AddPlaceMatch": {
            "labgrid.place.name": "placename",
            "labgrid.place.match.pattern": "pattern",
            "labgrid.place.match.rename": "rename",
        },
        "DeletePlaceMatch": {
            "labgrid.place.name": "placename",
            "labgrid.place.match.pattern": "pattern",
            "labgrid.place.match.rename": "rename",
        },
        "AcquirePlace": {
            "labgrid.place.name": "placename",
        },
        "LeasePlace": {
            "labgrid.place.name": "placename",
        },
        # "GetLeaseConfig": {},
        "ReleasePlace": {
            "labgrid.place.name": "placename",
            "labgrid.fromuser": "fromuser",
        },
        "AllowPlace": {
            "labgrid.place.name": "placename",
            "labgrid.place.share.user": "user",
        },
        "SharePlace": {
            "labgrid.place.name": "name",
            "labgrid.place.share.user": "user",
        },
        "UnsharePlace": {
            "labgrid.place.name": "name",
            "labgrid.place.share.user": "user",
        },
        "CreateReservation": {
            "labgrid.reservation.filters": "filters",
            "labgrid.reservation.priority": "prio",
        },
        "CancelReservation": {
            "labgrid.reservation.id": "token",
        },
        "PollReservation": {
            "labgrid.reservation.id": "token",
        },
        "RefreshReservation": {
            "labgrid.reservation.id": "reservation_id",
        },
        "ExtendLease": {
            "labgrid.reservation.id": "token",
        },
        # "GetReservations": {},
        "ListReservations": {
            "labgrid.request.filter": "filter",
            "labgrid.request.page_size": "page_size",
            "labgrid.request.page_token": "page_token",
        },
    }

    for rpc, metadata in attributes.items():
        old_rpc = getattr(coordinator, rpc)
        setattr(
            coordinator,
            rpc,
            instrument_rpc(old_rpc, metadata),
        )


def setup_otel_sdk_if_available(coordinator, exportercommand):
    """
    Setup gRPC tracing over OTLP and coordinator metrics over Prometheus and OTLP.

    These are only setup when the OpenTelemetry SDK modules are available.
    Existing TracerProvider and MeterProvider instances are reused instead of replaced.
    """
    global OTEL_SDK_INSTALLED
    if environ.get("OTEL_SDK_DISABLED", "").lower().strip() == "true":
        OTEL_SDK_INSTALLED = False
        return

    try:
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.exporter.prometheus import PrometheusMetricReader
        from opentelemetry.instrumentation.grpc import GrpcAioInstrumentorServer
        from opentelemetry.sdk.environment_variables import (
            OTEL_EXPORTER_PROMETHEUS_HOST,
            OTEL_EXPORTER_PROMETHEUS_PORT,
        )
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.trace import Resource, TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from prometheus_client import start_http_server

        resource = Resource.create({"service.name": "labgrid-coordinator"})
        if not isinstance(trace.get_tracer_provider(), TracerProvider):
            trace_exporters = _parse_exporters(
                environ.get("OTEL_TRACES_EXPORTER", ""),
                default={"otlp"},
                supported={"otlp"},
            )
            if trace_exporters:
                tracer_provider = TracerProvider(resource=resource)
                trace.set_tracer_provider(tracer_provider)
                if trace.get_tracer_provider() is not tracer_provider:
                    raise RuntimeError("Only the standard OpenTelemetry SDK TracerProvider is supported")
                tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))

        if not isinstance(metrics.get_meter_provider(), MeterProvider):
            metrics_exporters = _parse_exporters(
                environ.get("OTEL_METRICS_EXPORTER", ""),
                default={"prometheus"},
                supported={"prometheus", "otlp"},
            )
            if metrics_exporters:
                metric_readers = []
                if "prometheus" in metrics_exporters:
                    metric_readers.append(PrometheusMetricReader())
                if "otlp" in metrics_exporters:
                    metric_readers.append(PeriodicExportingMetricReader(OTLPMetricExporter()))
                meter_provider = MeterProvider(
                    resource=resource,
                    metric_readers=metric_readers,
                )
                metrics.set_meter_provider(meter_provider)
                if metrics.get_meter_provider() is not meter_provider:
                    raise RuntimeError("Only the standard OpenTelemetry SDK MeterProvider is supported")
                if "prometheus" in metrics_exporters:
                    start_http_server(
                        addr=environ.get(OTEL_EXPORTER_PROMETHEUS_HOST, "localhost"),
                        port=int(environ.get(OTEL_EXPORTER_PROMETHEUS_PORT, "9464")),
                    )

        grpc_server_instrumentor = GrpcAioInstrumentorServer()
        if not grpc_server_instrumentor.is_instrumented_by_opentelemetry:
            grpc_server_instrumentor.instrument()

        _monkeypatch_ExporterCommand_init(exportercommand)
        _monkeypatch_add_rpc_metadata(coordinator)

        LOGGER.debug("SDK installed and setup")

        OTEL_SDK_INSTALLED = True
    except ModuleNotFoundError:
        LOGGER.debug("No SDK installed")

        OTEL_SDK_INSTALLED = False


def setup_otel_metrics(coordinator_instance):
    """
    Register observable gauges for the coordinator state.

    The callbacks read the current state when Prometheus scrapes the metrics endpoint.
    """
    if not OTEL_SDK_INSTALLED:
        return

    meter = metrics.get_meter("labgrid.remote.coordinator")

    def observe_registered_places(_options):
        yield Observation(len(coordinator_instance.places))

    meter.create_observable_gauge(
        "labgrid_coordinator_places_registered",
        callbacks=[observe_registered_places],
        unit="1",
        description="Number of places registered with the coordinator.",
    )

    def observe_acquired_places(_options):
        places = list(coordinator_instance.places.values())
        yield Observation(sum(place.acquired is not None for place in places))

    meter.create_observable_gauge(
        "labgrid_coordinator_places_acquired",
        callbacks=[observe_acquired_places],
        unit="1",
        description="Number of places currently acquired from the coordinator.",
    )

    def observe_available_places(_options):
        places = list(coordinator_instance.places.values())
        yield Observation(sum(place.acquired is None and place.reservation is None for place in places))

    meter.create_observable_gauge(
        "labgrid_coordinator_places_available",
        callbacks=[observe_available_places],
        unit="1",
        description="Number of places currently available for scheduler allocation.",
    )

    def observe_waiting_reservations(_options):
        reservations = list(coordinator_instance.reservations.values())
        yield Observation(sum(reservation.state.name == "waiting" for reservation in reservations))

    meter.create_observable_gauge(
        "labgrid_coordinator_reservations_waiting",
        callbacks=[observe_waiting_reservations],
        unit="1",
        description="Number of reservations currently waiting for a matching place.",
    )

    def observe_allocated_reservations(_options):
        reservations = list(coordinator_instance.reservations.values())
        yield Observation(sum(bool(reservation.allocations) for reservation in reservations))

    meter.create_observable_gauge(
        "labgrid_coordinator_reservations_allocated",
        callbacks=[observe_allocated_reservations],
        unit="1",
        description="Number of reservations currently holding one or more place allocations.",
    )

    def observe_connected_exporters(_options):
        yield Observation(len(coordinator_instance.exporters))

    meter.create_observable_gauge(
        "labgrid_coordinator_exporters_connected",
        callbacks=[observe_connected_exporters],
        unit="1",
        description="Number of exporter sessions currently connected to the coordinator.",
    )

    def observe_registered_resources(_options):
        exporters = list(coordinator_instance.exporters.values())
        groups = [group for exporter in exporters for group in list(exporter.groups.values())]
        yield Observation(sum(len(group) for group in groups))

    meter.create_observable_gauge(
        "labgrid_coordinator_resources_registered",
        callbacks=[observe_registered_resources],
        unit="1",
        description="Number of resources currently registered by connected exporters.",
    )


def set_traceparent_in_metadata(out_msg, cmd):
    """
    Inject the `traceparent` and `tracestate` into an `ExporterOutMessage`'s
    `metatdata` field.

    Relies on `_monkeypatch_ExporterCommand_init` having been run by
    `setup_otel_sdk_if_available`.
    """
    LOGGER.debug("set_traceparent_in_metadata")
    if OTEL_SDK_INSTALLED:
        headers = {}
        propagate.inject(headers, context=cmd._otel_context)

        out_msg.metadata.traceparent = headers.get("traceparent", "")
        out_msg.metadata.tracestate = headers.get("tracestate", "")
