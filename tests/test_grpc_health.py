import asyncio
from types import SimpleNamespace

import pytest
from grpc_health.v1 import health

from labgrid.remote.grpc.health import HealthServicer


@pytest.mark.parametrize("emit_response", [False, True])
@pytest.mark.parametrize("outcome", ["complete", "error", "cancel"])
def test_health_watch_producer_completion(monkeypatch, emit_response, outcome):
    response = object()

    async def watch(self, request, context):
        assert context.peer() == "test-peer"
        if emit_response:
            await context.write(response)
        if outcome == "error":
            raise RuntimeError("producer failed")
        if outcome == "cancel":
            raise asyncio.CancelledError

    monkeypatch.setattr(health.aio.HealthServicer, "Watch", watch)

    async def run():
        tasks = asyncio.all_tasks()
        stream = HealthServicer().Watch(None, SimpleNamespace(peer=lambda: "test-peer"))
        try:
            if emit_response:
                assert await asyncio.wait_for(anext(stream), timeout=1) is response
            expected = {
                "complete": StopAsyncIteration,
                "error": RuntimeError,
                "cancel": asyncio.CancelledError,
            }[outcome]
            with pytest.raises(expected):
                await asyncio.wait_for(anext(stream), timeout=1)
        finally:
            await stream.aclose()
        assert asyncio.all_tasks() == tasks

    asyncio.run(run())


def test_health_watch_close_with_buffered_response(monkeypatch):
    async def run():
        tasks = asyncio.all_tasks()
        third_write_started = asyncio.Event()
        stopped = asyncio.Event()

        async def watch(self, request, context):
            try:
                await context.write(1)
                await context.write(2)
                third_write_started.set()
                await context.write(3)
                pytest.fail("The producer should block when the response buffer is full")
            finally:
                stopped.set()

        monkeypatch.setattr(health.aio.HealthServicer, "Watch", watch)
        stream = HealthServicer().Watch(None, None)
        try:
            assert await asyncio.wait_for(anext(stream), timeout=1) == 1
            await asyncio.wait_for(third_write_started.wait(), timeout=1)
        finally:
            await asyncio.wait_for(stream.aclose(), timeout=1)
        assert stopped.is_set()
        assert asyncio.all_tasks() == tasks

    asyncio.run(run())


def test_health_watch_cancel_while_waiting(monkeypatch):
    async def run():
        tasks = asyncio.all_tasks()
        started = asyncio.Event()
        stopped = asyncio.Event()

        async def watch(self, request, context):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()

        monkeypatch.setattr(health.aio.HealthServicer, "Watch", watch)
        stream = HealthServicer().Watch(None, None)
        reading = asyncio.create_task(anext(stream))
        try:
            await asyncio.wait_for(started.wait(), timeout=1)
        finally:
            reading.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(reading, timeout=1)
            await stream.aclose()
        assert stopped.is_set()
        assert asyncio.all_tasks() == tasks

    asyncio.run(run())
