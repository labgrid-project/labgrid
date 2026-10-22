"""Optional OpenTelemetry setup shared by the coordinator and exporter."""

import logging
import os
from functools import wraps

from opentelemetry import trace

from ..logging import MasqueradingLogExporter

LOGGER = logging.getLogger(__name__)
_enabled = False
_log_handler = None


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


def _setup_logging(resource):
    """Attach sanitized OTLP log export to the root logger once."""
    global _log_handler
    exporters = _parse_exporters(
        os.environ.get("OTEL_LOGS_EXPORTER", ""),
        default={"otlp"},
        supported={"otlp"},
    )
    if not exporters:
        return True

    root = logging.getLogger()
    if _log_handler in root.handlers:
        return True

    try:
        from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    except ImportError:
        LOGGER.debug("OpenTelemetry log exporter not installed")
        return False

    provider = LoggerProvider(resource=resource)
    exporter = MasqueradingLogExporter(OTLPLogExporter())
    provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
    _log_handler = LoggingHandler(logger_provider=provider)
    root.addHandler(_log_handler)
    return True


def setup_otel(service_name, *, with_metrics=False):
    """Configure telemetry when the optional ``otel`` dependencies are installed.

    Return whether the SDK is available and enabled, including when exporting is
    disabled with the ``OTEL_*_EXPORTER=none`` settings. An existing trace
    provider belongs to its caller and is reused without changing its resource
    or exporters.
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

    resource = Resource.create({"service.name": service_name}).merge(OTELResourceDetector().detect())
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
            provider = TracerProvider(resource=resource)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            trace.set_tracer_provider(provider)

    if not _setup_logging(resource):
        return False

    if with_metrics:
        from .otel_metrics import setup_metrics

        setup_metrics(resource)

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
