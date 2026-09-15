import asyncio
from contextlib import contextmanager

import pytest

import labgrid.remote.coordinator as coordinator_module
from labgrid.remote.identity import ClientIdentity


class RpcAbort(Exception):
    def __init__(self, code, details):
        super().__init__(details)
        self.code = code
        self.details = details


class RpcContext:
    async def abort(self, code, details):
        raise RpcAbort(code, details)

    def invocation_metadata(self):
        return ()

    def peer(self):
        pass


@pytest.fixture
def request_identity(monkeypatch):
    @contextmanager
    def set_request_identity(capabilities=None, identity_id="test-host/test-user"):
        hostname, _, name = identity_id.partition("/")
        identity = ClientIdentity(name, hostname, "pytest")
        identity.capabilities = capabilities

        with monkeypatch.context() as request_patch:
            request_patch.setattr(
                coordinator_module.ClientIdentity,
                "from_metadata",
                classmethod(lambda cls, metadata: identity),
            )
            yield identity

    return set_request_identity


@pytest.fixture
def capability_coordinator(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    loop = asyncio.new_event_loop()

    async def create_coordinator():
        return coordinator_module.Coordinator(use_capabilities=True)

    coordinator = loop.run_until_complete(create_coordinator())
    try:
        yield coordinator, loop
    finally:
        for task in coordinator.poll_tasks:
            task.cancel()
        loop.run_until_complete(asyncio.gather(*coordinator.poll_tasks, return_exceptions=True))
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
