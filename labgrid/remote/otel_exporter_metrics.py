"""Exporter measurements using the shared optional OpenTelemetry setup."""

from functools import partial

from opentelemetry.metrics import Observation

from .otel_metrics import get_meter


def _observe_resources(exporter, predicate, _options):
    counts = {}
    for group in list(exporter.groups.values()):
        for resource in list(group.values()):
            counts.setdefault(resource.cls, 0)
            if predicate(resource):
                counts[resource.cls] += 1
    for resource_class, count in counts.items():
        yield Observation(count, {"resource_class": resource_class})


def setup_exporter_metrics(exporter):
    """Register resource gauges and the command counter once per exporter."""
    meter = get_meter("labgrid.remote.exporter")
    if meter is None or hasattr(exporter, "_otel_resource_commands"):
        return

    gauges = [
        ("configured", lambda resource: True, "Number of resources configured on the exporter."),
        (
            "free",
            lambda resource: not getattr(resource, "broken", None) and resource.avail and resource.acquired is None,
            "Number of available, unacquired resources on the exporter.",
        ),
        (
            "unavailable",
            lambda resource: not getattr(resource, "broken", None) and not resource.avail,
            "Number of unavailable, non-broken resources on the exporter.",
        ),
        (
            "acquired",
            lambda resource: not getattr(resource, "broken", None) and resource.acquired is not None,
            "Number of resources acquired by a place on the exporter.",
        ),
        (
            "broken",
            lambda resource: bool(getattr(resource, "broken", None)),
            "Number of permanently broken resources on the exporter.",
        ),
    ]
    for name, predicate, description in gauges:
        meter.create_observable_gauge(
            f"labgrid_exporter_resources_{name}",
            callbacks=[partial(_observe_resources, exporter, predicate)],
            unit="1",
            description=description,
        )
    exporter._otel_resource_commands = meter.create_counter(
        "labgrid_exporter_resource_commands_total",
        unit="1",
        description="Number of resource command results.",
    )


def record_resource_command(exporter, operation, success):
    """Count a completed acquire/release attempt using bounded labels."""
    counter = getattr(exporter, "_otel_resource_commands", None)
    if counter is not None:
        counter.add(1, {"operation": operation, "outcome": "success" if success else "failure"})
