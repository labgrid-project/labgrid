import logging
from functools import wraps

from opentelemetry import trace

OTEL_SDK_INSTALLED = False

LOGGER = logging.getLogger("otel")


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


def setup_otel_sdk_if_available(coordinator):
    """
    Setup gRPC AIO Server instrumentation and OTEL Span exporting over OTLP.

    These are only setup when the OpenTelemetry SDK modules are available.
    """
    global OTEL_SDK_INSTALLED
    try:
        from opentelemetry.instrumentation.grpc import GrpcAioInstrumentorServer
        from opentelemetry.sdk.trace import TracerProvider, Resource
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        resource = Resource.create({"service.name": "labgrid-coordinator"})
        trace.set_tracer_provider(TracerProvider(resource=resource))
        trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))

        grpc_server_instrumentor = GrpcAioInstrumentorServer()
        grpc_server_instrumentor.instrument()

        _monkeypatch_add_rpc_metadata(coordinator)

        LOGGER.debug("SDK installed and setup")

        OTEL_SDK_INSTALLED = True
    except ModuleNotFoundError:
        LOGGER.debug("No SDK installed")

        OTEL_SDK_INSTALLED = False
