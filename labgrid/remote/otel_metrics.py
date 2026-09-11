"""Optional metric exporting shared by the coordinator and exporter."""

import logging
from os import environ
from weakref import WeakSet

from opentelemetry import metrics
from opentelemetry.metrics import Observation

from .otel import _parse_exporters

LOGGER = logging.getLogger(__name__)
_meter_provider = None


def setup_metrics(resource):
    """Configure metric readers once, or reuse an application's SDK provider.

    Prometheus is enabled by default. ``OTEL_METRICS_EXPORTER`` also accepts
    ``otlp``, ``prometheus,otlp``, and ``none``. The normal OTel environment
    variables configure the exporters; no collector address is hardcoded.
    """
    global _meter_provider
    _meter_provider = None
    if environ.get("OTEL_SDK_DISABLED", "").strip().lower() == "true":
        return False
    selected = _parse_exporters(
        environ.get("OTEL_METRICS_EXPORTER", ""), default={"prometheus"}, supported={"prometheus", "otlp"}
    )
    if not selected:
        return False

    try:
        from opentelemetry.sdk.metrics import MeterProvider
    except ImportError:
        LOGGER.debug("OpenTelemetry metrics SDK is not installed")
        return False

    provider = metrics.get_meter_provider()
    if isinstance(provider, MeterProvider):
        _meter_provider = provider
        return True

    readers = []
    try:
        if "prometheus" in selected:
            from opentelemetry.exporter.prometheus import PrometheusMetricReader
            from prometheus_client import start_http_server

            readers.append(PrometheusMetricReader())
        if "otlp" in selected:
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
            from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

            readers.append(PeriodicExportingMetricReader(OTLPMetricExporter()))
    except ImportError:
        for reader in readers:
            reader.shutdown()
        LOGGER.warning("OpenTelemetry metrics exporter is not installed")
        return False

    provider = MeterProvider(resource=resource, metric_readers=readers)
    metrics.set_meter_provider(provider)
    if metrics.get_meter_provider() is not provider:
        provider.shutdown()
        raise RuntimeError("An unsupported OpenTelemetry MeterProvider is already configured")

    if "prometheus" in selected:
        start_http_server(
            addr=environ.get("OTEL_EXPORTER_PROMETHEUS_HOST", "localhost"),
            port=int(environ.get("OTEL_EXPORTER_PROMETHEUS_PORT", "9464")),
        )
    _meter_provider = provider
    return True


def get_meter(scope):
    """Return a meter if metric collection was enabled during startup."""
    if _meter_provider is None:
        return None
    return _meter_provider.get_meter(scope)


def setup_coordinator_metrics(coordinator):
    """Register gauges which read current coordinator state at collection time."""
    meter = get_meter("labgrid.remote.coordinator")
    if meter is None or hasattr(coordinator, "_otel_reservation_wait_duration"):
        return

    coordinator._otel_reservation_wait_duration = (
        meter.create_histogram(
            "labgrid_coordinator_reservation_wait_duration_seconds",
            unit="s",
            description="Time from reservation creation until first allocation.",
        ),
        WeakSet(),
    )

    def observe_registered_places(_options):
        yield Observation(len(coordinator.places))

    meter.create_observable_gauge(
        "labgrid_coordinator_places_registered",
        callbacks=[observe_registered_places],
        unit="1",
        description="Number of places registered with the coordinator.",
    )

    def observe_acquired_places(_options):
        places = list(coordinator.places.values())
        yield Observation(sum(place.acquired is not None for place in places))

    meter.create_observable_gauge(
        "labgrid_coordinator_places_acquired",
        callbacks=[observe_acquired_places],
        unit="1",
        description="Number of places currently acquired from the coordinator.",
    )

    def observe_available_places(_options):
        places = list(coordinator.places.values())
        yield Observation(sum(place.acquired is None and place.reservation is None for place in places))

    meter.create_observable_gauge(
        "labgrid_coordinator_places_available",
        callbacks=[observe_available_places],
        unit="1",
        description="Number of places currently available for scheduler allocation.",
    )

    def observe_waiting_reservations(_options):
        reservations = list(coordinator.reservations.values())
        yield Observation(sum(reservation.state.name == "waiting" for reservation in reservations))

    meter.create_observable_gauge(
        "labgrid_coordinator_reservations_waiting",
        callbacks=[observe_waiting_reservations],
        unit="1",
        description="Number of reservations currently waiting for a matching place.",
    )

    def observe_allocated_reservations(_options):
        reservations = list(coordinator.reservations.values())
        yield Observation(sum(bool(reservation.allocations) for reservation in reservations))

    meter.create_observable_gauge(
        "labgrid_coordinator_reservations_allocated",
        callbacks=[observe_allocated_reservations],
        unit="1",
        description="Number of reservations currently holding one or more place allocations.",
    )

    def observe_connected_exporters(_options):
        yield Observation(len(coordinator.exporters))

    meter.create_observable_gauge(
        "labgrid_coordinator_exporters_connected",
        callbacks=[observe_connected_exporters],
        unit="1",
        description="Number of exporter sessions currently connected to the coordinator.",
    )

    def observe_registered_resources(_options):
        exporters = list(coordinator.exporters.values())
        groups = [group for exporter in exporters for group in list(exporter.groups.values())]
        yield Observation(sum(len(group) for group in groups))

    meter.create_observable_gauge(
        "labgrid_coordinator_resources_registered",
        callbacks=[observe_registered_resources],
        unit="1",
        description="Number of resources currently registered by connected exporters.",
    )


def record_reservation_wait_duration(coordinator, reservation, duration):
    """Record only a reservation's first allocation, without retaining it."""
    instruments = getattr(coordinator, "_otel_reservation_wait_duration", None)
    if instruments is None:
        return
    histogram, observed = instruments
    if reservation not in observed:
        histogram.record(max(0.0, duration))
        observed.add(reservation)
