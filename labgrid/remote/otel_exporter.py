import logging
from os import environ

from opentelemetry import context, metrics, propagate, trace
from opentelemetry.metrics import Observation

OTEL_SDK_INSTALLED = False

RESOURCE_COMMANDS_COUNTER = None

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


def setup_otel_sdk_if_available():
    """
    Setup gRPC tracing and metrics over OTLP, and metrics over Prometheus.

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
        from opentelemetry.sdk.environment_variables import (
            OTEL_EXPORTER_PROMETHEUS_HOST,
            OTEL_EXPORTER_PROMETHEUS_PORT,
        )
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.trace import Resource, TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from prometheus_client import start_http_server

        resource = Resource.create({"service.name": "labgrid-exporter"})
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

        LOGGER.debug("SDK installed and setup")

        OTEL_SDK_INSTALLED = True
    except ModuleNotFoundError:
        LOGGER.debug("No SDK installed")

        OTEL_SDK_INSTALLED = False


def setup_otel_metrics(exporter_instance):
    """Register observable gauges for the exporter resource state."""
    global RESOURCE_COMMANDS_COUNTER
    if not OTEL_SDK_INSTALLED:
        return

    meter = metrics.get_meter("labgrid.remote.exporter")

    def observe_configured_resources(_options):
        counts = {}
        for group in list(exporter_instance.groups.values()):
            for resource in list(group.values()):
                counts.setdefault(resource.cls, 0)
                counts[resource.cls] += 1

        for resource_class, count in counts.items():
            yield Observation(count, {"resource_class": resource_class})

    meter.create_observable_gauge(
        "labgrid_exporter_resources_configured",
        callbacks=[observe_configured_resources],
        unit="1",
        description="Number of resources configured on the exporter.",
    )

    def observe_free_resources(_options):
        counts = {}
        for group in list(exporter_instance.groups.values()):
            for resource in list(group.values()):
                counts.setdefault(resource.cls, 0)
                if not getattr(resource, "broken", None) and resource.avail and resource.acquired is None:
                    counts[resource.cls] += 1

        for resource_class, count in counts.items():
            yield Observation(count, {"resource_class": resource_class})

    meter.create_observable_gauge(
        "labgrid_exporter_resources_free",
        callbacks=[observe_free_resources],
        unit="1",
        description="Number of available, unacquired resources on the exporter.",
    )

    def observe_unavailable_resources(_options):
        counts = {}
        for group in list(exporter_instance.groups.values()):
            for resource in list(group.values()):
                counts.setdefault(resource.cls, 0)
                if not getattr(resource, "broken", None) and not resource.avail:
                    counts[resource.cls] += 1

        for resource_class, count in counts.items():
            yield Observation(count, {"resource_class": resource_class})

    meter.create_observable_gauge(
        "labgrid_exporter_resources_unavailable",
        callbacks=[observe_unavailable_resources],
        unit="1",
        description="Number of unavailable, non-broken resources on the exporter.",
    )

    def observe_acquired_resources(_options):
        counts = {}
        for group in list(exporter_instance.groups.values()):
            for resource in list(group.values()):
                counts.setdefault(resource.cls, 0)
                if not getattr(resource, "broken", None) and resource.acquired is not None:
                    counts[resource.cls] += 1

        for resource_class, count in counts.items():
            yield Observation(count, {"resource_class": resource_class})

    meter.create_observable_gauge(
        "labgrid_exporter_resources_acquired",
        callbacks=[observe_acquired_resources],
        unit="1",
        description="Number of resources acquired by a place on the exporter.",
    )

    def observe_broken_resources(_options):
        counts = {}
        for group in list(exporter_instance.groups.values()):
            for resource in list(group.values()):
                counts.setdefault(resource.cls, 0)
                if getattr(resource, "broken", None):
                    counts[resource.cls] += 1

        for resource_class, count in counts.items():
            yield Observation(count, {"resource_class": resource_class})

    meter.create_observable_gauge(
        "labgrid_exporter_resources_broken",
        callbacks=[observe_broken_resources],
        unit="1",
        description="Number of permanently broken resources on the exporter.",
    )

    RESOURCE_COMMANDS_COUNTER = meter.create_counter(
        "labgrid_exporter_resource_commands_total",
        unit="1",
        description="Number of resource command results.",
    )


def record_resource_command(operation, success):
    """Record the result of a resource command handled by the exporter."""
    if not OTEL_SDK_INSTALLED:
        return

    RESOURCE_COMMANDS_COUNTER.add(
        1,
        {"operation": operation, "outcome": "success" if success else "failure"},
    )


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
