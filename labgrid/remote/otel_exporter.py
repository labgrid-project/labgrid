"""Trace context propagation for commands carried by the exporter stream."""

from opentelemetry import context, propagate, trace


def inject_trace_context(out_message, trace_context):
    """Attach the context captured when a coordinator command was queued."""
    carrier = {}
    propagate.inject(carrier, context=trace_context)
    if traceparent := carrier.get("traceparent"):
        out_message.metadata.traceparent = traceparent
        out_message.metadata.tracestate = carrier.get("tracestate", "")


def start_span_from_metadata(out_message, tracer):
    """Start a command span independently of the long-lived stream's context.

    An older coordinator sends no metadata. In that case (or for invalid
    metadata), start a new trace instead of parenting it to the receiver task.
    Only the OpenTelemetry API is needed, so this also works without the SDK.
    """
    parent = propagate.extract(
        {
            "traceparent": out_message.metadata.traceparent,
            "tracestate": out_message.metadata.tracestate,
        },
        context=context.Context(),
    )
    request = out_message.set_acquired_request
    return tracer.start_as_current_span(
        "set_acquired_request",
        context=parent,
        kind=trace.SpanKind.SERVER,
        attributes={
            "labgrid.resource.group_name": request.group_name,
            "labgrid.resource.resource_name": request.resource_name,
            "labgrid.resource.place_name": request.place_name,
            "labgrid.exporter.operation": "acquire" if request.place_name else "release",
        },
    )
