import asyncio
from contextlib import contextmanager
from typing import Optional, Callable

import grpc
import pytest

import labgrid.remote.coordinator as coordinator_module
from labgrid.remote.auth.capability import Capability
from labgrid.remote.generated import labgrid_coordinator_pb2
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


# region CreatePlace
async def CreatePlace(coordinator):
    await coordinator.CreatePlace(labgrid_coordinator_pb2.CreatePlaceRequest(name="test"), RpcContext())


def CreatePlace_fail(coordinator):
    assert "test" not in coordinator.places


def CreatePlace_success(coordinator):
    assert "test" in coordinator.places


# endregion


# region GetPlace
async def GetPlace(coordinator):
    await coordinator.GetPlace(labgrid_coordinator_pb2.GetPlaceRequest(name="test"), RpcContext())


async def GetPlace_setup(coordinator):
    await coordinator.CreatePlace(labgrid_coordinator_pb2.CreatePlaceRequest(name="test"), RpcContext())


# endregion


# region ListResources
async def ListResources(coordinator):
    await coordinator.ListResources(labgrid_coordinator_pb2.ListResourcesRequest(), RpcContext())


# endregion


@pytest.mark.parametrize(
    [
        "capabilities_enabled",  # Should the Coordinator have Capabilities enabled
        "identity_capability_set",  # The Capabilities to include in the identity making the test request
        "expected_error_status",  # The error to expect, if applicable
        "setup_func",  # The function to setup the Coordinator for the test
        "request_func",  # The function to call the request
        "verifier_func",  # The function to verify the Coordinator state after the request_func,
        "identity_id",  # The id of the Identity
    ],
    [
        # CreatePlace
        (True, {Capability.create_place}, None, None, CreatePlace, CreatePlace_success, "testhost/testuser"),
        (True, set(), grpc.StatusCode.PERMISSION_DENIED, None, CreatePlace, CreatePlace_fail, "testhost/testuser"),
        (False, set(), None, None, CreatePlace, CreatePlace_success, "testhost/testuser"),
        # GetPlace
        (True, {Capability.get_place}, None, GetPlace_setup, GetPlace, None, "testhost/testuser"),
        (True, set(), grpc.StatusCode.PERMISSION_DENIED, GetPlace_setup, GetPlace, None, "testhost/testuser"),
        (False, set(), None, GetPlace_setup, GetPlace, None, "testhost/testuser"),
        # ListResources
        (True, {Capability.list_resources}, None, None, ListResources, None, "testhost/testuser"),
        (True, set(), grpc.StatusCode.PERMISSION_DENIED, None, ListResources, None, "testhost/testuser"),
        (False, set(), None, None, ListResources, None, "testhost/testuser"),
    ],
)
def test_capability_behaviour(
    capability_coordinator,
    request_identity,
    capabilities_enabled: bool,
    identity_capability_set: set[Capability],
    expected_error_status: Optional[grpc.StatusCode],
    setup_func: Callable,
    request_func: Callable,
    verifier_func: Callable,
    identity_id: str,
):
    coordinator, loop = capability_coordinator

    if setup_func:
        with request_identity(capabilities={member.value for member in Capability}):
            loop.run_until_complete(setup_func(coordinator))

    coordinator.use_capabilities = capabilities_enabled

    if expected_error_status:
        with (
            request_identity(capabilities=identity_capability_set, identity_id=identity_id),
            pytest.raises(RpcAbort) as exc_info,
        ):
            loop.run_until_complete(request_func(coordinator))

        assert exc_info.value.code == expected_error_status
    else:
        with request_identity(capabilities=identity_capability_set, identity_id=identity_id):
            loop.run_until_complete(request_func(coordinator))

    if verifier_func:
        verifier_func(coordinator)
