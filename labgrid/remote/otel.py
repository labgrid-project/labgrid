"""Optional OpenTelemetry setup shared by the coordinator and exporter."""

import logging
import os
from functools import wraps

from opentelemetry import trace

LOGGER = logging.getLogger(__name__)
_enabled = False


def _parse_exporters(value, *, default, supported):
    """Validate a comma-separated OpenTelemetry exporter setting."""
    if not value.strip():
        return default
    selected = {item.strip().lower() for item in value.split(",")}
    if selected == {"none"}:
        return set()
    if selected - supported:
        raise ValueError(f"Unsupported OpenTelemetry exporters: {sorted(selected - supported)}")
    return selected


def setup_otel(service_name):
    """Configure tracing when the optional ``otel`` dependencies are installed.

    Return whether the SDK is available and enabled, including when exporting is
    disabled with ``OTEL_TRACES_EXPORTER=none``. An existing provider belongs to
    its caller and is reused without changing its resource or exporters.
    """
    global _enabled
    _enabled = False
    if os.environ.get("OTEL_SDK_DISABLED", "").strip().lower() == "true":
        return False

    try:
        from opentelemetry.sdk.resources import OTELResourceDetector, Resource
        from opentelemetry.sdk.trace import TracerProvider
    except ImportError:
        LOGGER.debug("OpenTelemetry SDK not installed")
        return False

    if isinstance(trace.get_tracer_provider(), trace.ProxyTracerProvider):
        exporters = _parse_exporters(os.environ.get("OTEL_TRACES_EXPORTER", ""), default={"otlp"}, supported={"otlp"})
        if exporters:
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
                from opentelemetry.sdk.trace.export import BatchSpanProcessor
            except ImportError:
                LOGGER.debug("OpenTelemetry OTLP exporter not installed")
                return False

            # The exporter reads the standard OTLP environment variables and
            # defaults to localhost:4317. Environment resource attributes take
            # precedence over the component's default service name.
            exporter = OTLPSpanExporter()
            resource = Resource.create({"service.name": service_name}).merge(OTELResourceDetector().detect())
            provider = TracerProvider(resource=resource)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            trace.set_tracer_provider(provider)

    _enabled = True
    return True


def instrument_grpc_server():
    """Instrument subsequently created gRPC AIO servers once the SDK is enabled."""
    if not _enabled:
        return False

    try:
        from opentelemetry.instrumentation.grpc import GrpcAioInstrumentorServer
    except ImportError:
        LOGGER.debug("OpenTelemetry gRPC instrumentation not installed")
        return False

    instrumentor = GrpcAioInstrumentorServer()
    if not instrumentor.is_instrumented_by_opentelemetry:
        instrumentor.instrument()
    return True


def instrument_rpc(metadata):
    """Add selected request fields to the active gRPC span of a unary RPC."""

    def decorate(rpc):
        @wraps(rpc)
        async def wrapper(self, request, *args, **kwargs):
            span = trace.get_current_span()
            if span.is_recording():
                for attribute, field in metadata.items():
                    value = getattr(request, field, None)
                    if value is None or value == "":
                        continue
                    if not isinstance(value, (str, bool, int, float)):
                        value = str(value)
                    span.set_attribute(attribute, value)
            return await rpc(self, request, *args, **kwargs)

        return wrapper

    return decorate
