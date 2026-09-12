"""Trace continuity and backwards compatibility across the exporter stream."""

import asyncio
import subprocess
import sys
import textwrap
from contextlib import suppress
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
from opentelemetry import context, trace

from labgrid.remote import exporter as exporter_module
from labgrid.remote.common import queue_as_aiter
from labgrid.remote.coordinator import Coordinator, ExporterCommand
from labgrid.remote.exporter import BrokenResourceError, Exporter, InvalidResourceRequestError, UnknownResourceError
from labgrid.remote.generated import labgrid_coordinator_pb2 as pb2


@pytest.fixture
def tracing(monkeypatch):
    monkeypatch.setenv("OTEL_SDK_DISABLED", "false")
    sdk_trace = pytest.importorskip("opentelemetry.sdk.trace")
    sdk_export = pytest.importorskip("opentelemetry.sdk.trace.export")
    memory_export = pytest.importorskip("opentelemetry.sdk.trace.export.in_memory_span_exporter")
    memory = memory_export.InMemorySpanExporter()
    provider = sdk_trace.TracerProvider()
    provider.add_span_processor(sdk_export.SimpleSpanProcessor(memory))
    tracer = provider.get_tracer("test-exporter")
    monkeypatch.setattr(exporter_module, "tracer", tracer)
    yield tracer, memory
    provider.shutdown()


def make_exporter():
    # No channel or hardware is needed to exercise received command handling.
    exporter = object.__new__(Exporter)
    exporter.out_queue = asyncio.Queue()
    exporter.acquire = AsyncMock()
    exporter.release = AsyncMock()
    return exporter


def make_message(operation):
    message = pb2.ExporterOutMessage()
    message.set_acquired_request.group_name = "group"
    message.set_acquired_request.resource_name = "resource"
    if operation == "acquire":
        message.set_acquired_request.place_name = "place"
    return message


@pytest.mark.parametrize("operation", ["acquire", "release"])
def test_command_keeps_rpc_parent_across_stream_queue(tracing, operation):
    tracer, memory = tracing

    async def run():
        coordinator = object.__new__(Coordinator)
        coordinator.exporters = {}
        coordinator.clients = {}
        coordinator.loop = asyncio.get_running_loop()
        request_queue = asyncio.Queue()
        rpc_context = SimpleNamespace(peer=lambda: "exporter", done=lambda: False, cancelled=lambda: False)
        stream = coordinator.ExporterStream(queue_as_aiter(request_queue), rpc_context)
        assert (await anext(stream)).WhichOneof("kind") == "hello"

        startup = pb2.ExporterInMessage()
        startup.startup.name = "test-exporter"
        startup.startup.version = "test"
        request_queue.put_nowait(startup)

        with tracer.start_as_current_span("stream-receiver", context=context.Context()) as receiver:
            receive_task = asyncio.create_task(anext(stream))
        while "exporter" not in coordinator.exporters:
            await asyncio.sleep(0)

        parent_context = trace.SpanContext(
            trace_id=0x1234567890ABCDEF1234567890ABCDEF,
            span_id=0x1234567890ABCDEF,
            is_remote=True,
            trace_flags=trace.TraceFlags(1),
            trace_state=trace.TraceState([("test", "value")]),
        )
        parent = trace.set_span_in_context(trace.NonRecordingSpan(parent_context), context.Context())
        with tracer.start_as_current_span("place-rpc", context=parent) as rpc:
            command = ExporterCommand(make_message(operation).set_acquired_request)
        # The creating RPC has ended before another task dequeues the command.
        coordinator.exporters["exporter"].queue.put_nowait(command)

        try:
            out_message = await receive_task
            assert out_message.metadata.tracestate == "test=value"
            exporter = make_exporter()
            with trace.use_span(receiver):
                await exporter._handle_set_acquired_request(out_message)
            assert exporter.out_queue.get_nowait().response.success
            return rpc.get_span_context(), receiver.get_span_context()
        finally:
            request_queue.put_nowait(None)
            await asyncio.sleep(0)
            with suppress(asyncio.CancelledError):
                await stream.aclose()

    rpc, receiver = asyncio.run(asyncio.wait_for(run(), timeout=5))
    span = next(span for span in memory.get_finished_spans() if span.name == "set_acquired_request")
    assert span.context.trace_id == rpc.trace_id
    assert span.parent.span_id == rpc.span_id
    assert span.parent.is_remote
    assert span.parent.trace_state.get("test") == "value"
    assert span.context.trace_id != receiver.trace_id


@pytest.mark.parametrize("operation", ["acquire", "release"])
@pytest.mark.parametrize("metadata", [None, "invalid-traceparent"])
def test_legacy_or_invalid_metadata_starts_independent_trace(tracing, operation, metadata):
    tracer, memory = tracing

    async def run():
        exporter = make_exporter()
        message = make_message(operation)
        if metadata is not None:
            message.metadata.traceparent = metadata
        with tracer.start_as_current_span("unrelated-receiver") as receiver:
            await exporter._handle_set_acquired_request(message)
        return receiver.get_span_context()

    receiver = asyncio.run(run())
    span = next(span for span in memory.get_finished_spans() if span.name == "set_acquired_request")
    assert span.parent is None
    assert span.context.trace_id != receiver.trace_id


@pytest.mark.parametrize("operation", ["acquire", "release"])
@pytest.mark.parametrize("error_type", [None, BrokenResourceError, InvalidResourceRequestError, UnknownResourceError])
def test_exporter_command_status_and_response(tracing, operation, error_type):
    _, memory = tracing

    async def run():
        exporter = make_exporter()
        method = getattr(exporter, operation)
        if error_type:
            method.side_effect = error_type("cannot handle command")
        await exporter._handle_set_acquired_request(make_message(operation))
        if operation == "acquire":
            method.assert_awaited_once_with("group", "resource", "place")
            exporter.release.assert_not_awaited()
        else:
            method.assert_awaited_once_with("group", "resource")
            exporter.acquire.assert_not_awaited()
        return exporter.out_queue.get_nowait().response

    response = asyncio.run(run())
    (span,) = memory.get_finished_spans()
    assert span.kind == trace.SpanKind.SERVER
    assert span.attributes["labgrid.exporter.operation"] == operation
    assert span.attributes["labgrid.resource.group_name"] == "group"
    assert span.attributes["labgrid.resource.resource_name"] == "resource"
    assert span.attributes["labgrid.resource.place_name"] == ("place" if operation == "acquire" else "")
    assert response.success is (error_type is None)
    if error_type:
        assert response.reason == "cannot handle command"
        assert span.status.status_code == trace.StatusCode.ERROR
        assert span.status.description == response.reason
        assert span.events[0].name == "exception"
        assert span.events[0].attributes["exception.message"] == response.reason
    else:
        assert not response.HasField("reason")
        assert span.status.status_code == trace.StatusCode.OK
        assert not span.events


@pytest.mark.parametrize("operation", ["acquire", "release"])
def test_unexpected_error_keeps_upstream_exception_behavior(tracing, operation):
    _, memory = tracing

    async def run():
        exporter = make_exporter()
        getattr(exporter, operation).side_effect = RuntimeError("unexpected failure")
        with pytest.raises(RuntimeError, match="unexpected failure"):
            await exporter._handle_set_acquired_request(make_message(operation))
        assert not exporter.out_queue.get_nowait().response.success

    asyncio.run(run())
    (span,) = memory.get_finished_spans()
    assert span.status.status_code == trace.StatusCode.ERROR
    assert span.events[0].attributes["exception.message"] == "unexpected failure"


def test_trace_metadata_is_compatible_with_legacy_wire_format():
    # Build the pre-tracing descriptor, so both decoding directions are tested
    # without keeping a second generated protobuf module in the source tree.
    descriptor = descriptor_pb2.FileDescriptorProto.FromString(pb2.DESCRIPTOR.serialized_pb)
    for message in list(descriptor.message_type):
        if message.name == "Metadata":
            descriptor.message_type.remove(message)
        elif message.name == "ExporterOutMessage":
            for field in list(message.field):
                if field.name == "metadata":
                    assert field.number == 5
                    message.field.remove(field)
    pool = descriptor_pool.DescriptorPool()
    pool.Add(descriptor)
    legacy_type = message_factory.GetMessageClass(pool.FindMessageTypeByName("labgrid.ExporterOutMessage"))

    current = make_message("acquire")
    current.metadata.traceparent = "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01"
    legacy = legacy_type.FromString(current.SerializeToString())
    assert legacy.WhichOneof("kind") == "set_acquired_request"
    assert legacy.set_acquired_request.place_name == "place"

    legacy.DiscardUnknownFields()
    restored = pb2.ExporterOutMessage.FromString(legacy.SerializeToString())
    assert restored.WhichOneof("kind") == "set_acquired_request"
    assert restored.set_acquired_request == current.set_acquired_request
    assert not restored.HasField("metadata")


def test_exporter_commands_work_without_sdk():
    script = textwrap.dedent("""
        import asyncio
        import builtins
        import os
        from unittest.mock import AsyncMock

        os.environ['OTEL_SDK_DISABLED'] = 'false'
        real_import = builtins.__import__
        def without_sdk(name, *args, **kwargs):
            if name.startswith('opentelemetry.sdk') or name.startswith('opentelemetry.exporter'):
                raise ModuleNotFoundError(name, name=name)
            return real_import(name, *args, **kwargs)
        builtins.__import__ = without_sdk

        from labgrid.remote.coordinator import ExporterCommand
        from labgrid.remote.exporter import Exporter
        from labgrid.remote.generated import labgrid_coordinator_pb2 as pb2
        from labgrid.remote.otel import setup_otel
        from labgrid.remote.otel_exporter import inject_trace_context
        assert setup_otel('labgrid-exporter') is False

        async def run():
            exporter = object.__new__(Exporter)
            exporter.out_queue = asyncio.Queue()
            exporter.acquire = AsyncMock()
            exporter.release = AsyncMock()
            for place in ('place', ''):
                message = pb2.ExporterOutMessage()
                message.set_acquired_request.group_name = 'group'
                message.set_acquired_request.resource_name = 'resource'
                message.set_acquired_request.place_name = place
                command = ExporterCommand(message.set_acquired_request)
                inject_trace_context(message, command.trace_context)
                assert not message.HasField('metadata')
                await exporter._handle_set_acquired_request(message)
                assert exporter.out_queue.get_nowait().response.success
            exporter.acquire.assert_awaited_once_with('group', 'resource', 'place')
            exporter.release.assert_awaited_once_with('group', 'resource')
        asyncio.run(run())
    """)
    subprocess.run([sys.executable, "-c", script], check=True, timeout=20)
