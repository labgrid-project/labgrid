"""Adapt async health Watch for interceptors expecting an async generator."""

import asyncio

from grpc_health.v1 import health, health_pb2


class _WatchContext:
    """Forward context operations, buffering writes for the Watch generator."""

    def __init__(self, context, responses):
        self._context = context
        self._responses = responses

    def __getattr__(self, name):
        return getattr(self._context, name)

    async def write(self, response):
        await self._responses.put(response)


class HealthServicer(health.aio.HealthServicer):
    """Keep reference health state while yielding Watch responses for tracing.

    The reference Watch uses context.write(), which some streaming interceptors
    do not support. Delegate it through a bounded queue rather than duplicating
    its status and watcher management. See grpc/grpc#28728.
    """

    def __init__(self, service_names=("",)):
        super().__init__()
        self._service_names = tuple(service_names)

    @classmethod
    async def create(cls, service_names):
        """Create a servicer with the given services initially NOT_SERVING."""
        servicer = cls(service_names)
        for service_name in servicer._service_names:
            await servicer.set(service_name, health_pb2.HealthCheckResponse.NOT_SERVING)
        return servicer

    async def mark_serving(self):
        """Publish SERVING for all configured service names."""
        for service_name in self._service_names:
            await self.set(service_name, health_pb2.HealthCheckResponse.SERVING)

    async def Watch(self, request, context):
        responses = asyncio.Queue(maxsize=1)
        producer = asyncio.create_task(super().Watch(request, _WatchContext(context, responses)))
        reader = None
        try:
            while True:
                reader = asyncio.create_task(responses.get())
                await asyncio.wait((reader, producer), return_when=asyncio.FIRST_COMPLETED)
                # Deliver a queued response even if the producer also finished.
                if reader.done() or not responses.empty():
                    yield await reader
                    reader = None
                else:
                    await producer  # Propagate failure or normal completion.
                    return
        finally:
            tasks = [producer]
            if reader is not None:
                tasks.append(reader)
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
