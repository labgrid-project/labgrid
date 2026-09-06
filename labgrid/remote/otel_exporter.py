import logging
from os import environ

from opentelemetry import context, propagate, trace

OTEL_SDK_INSTALLED = False

LOGGER = logging.getLogger("otel")


def setup_otel_sdk_if_available():
    """
    Setup gRPC AIO Server instrumentation and OTEL Span exporting over OTLP.

    These are only setup when the OpenTelemetry SDK modules are available.
    """
    global OTEL_SDK_INSTALLED
    if environ.get("OTEL_SDK_DISABLED", "").lower().strip() == "true":
        OTEL_SDK_INSTALLED = False
        return

    try:
        from opentelemetry.sdk.trace import TracerProvider, Resource
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        resource = Resource.create({"service.name": "labgrid-exporter"})
        trace.set_tracer_provider(TracerProvider(resource=resource))
        trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))

        LOGGER.debug("SDK installed and setup")

        OTEL_SDK_INSTALLED = True
    except ModuleNotFoundError:
        LOGGER.debug("No SDK installed")

        OTEL_SDK_INSTALLED = False


def start_span_from_metadata(out_msg, tracer):
    if not OTEL_SDK_INSTALLED:
        return tracer.start_as_current_span("out_message")

    carrier = {
        "traceparent": out_msg.metadata.traceparent,
        "tracestate": out_msg.metadata.tracestate,
    }
    parent_context = propagate.extract(
        carrier,
        context=context.Context(),
    )

    return tracer.start_as_current_span(
        "out_message",
        context=parent_context,
        kind=trace.SpanKind.SERVER,
    )
