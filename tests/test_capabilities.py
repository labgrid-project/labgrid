import argparse
import asyncio

import grpc
import pytest
import pytest_asyncio

from labgrid.remote.auth.capability import Capability
from labgrid.remote.coordinator import Coordinator
from labgrid.remote.client import ClientSession, ServerError, UserError
from labgrid.remote.generated import labgrid_coordinator_pb2
from labgrid.remote.generated import labgrid_coordinator_pb2_grpc
from labgrid.remote.grpc.interceptor.client import IdentityClientStreamStreamInterceptor
from labgrid.remote.identity import ClientIdentity

def revoke_capabilities(coordinator, identity_id, *capabilities):
    assert(hasattr(coordinator, "revoked_capabilities"))
    assert(coordinator.revoked_capabilities.get(identity_id, None) is None)
    coordinator.revoked_capabilities[identity_id] = set(capabilities)

@pytest_asyncio.fixture(loop_scope='function')
async def async_coordinator(monkeypatch):

    class RevocableClientIdentity(ClientIdentity):
        @classmethod
        def from_metadata(cls, metadata):
            identity = super().from_metadata(metadata)
            if identity:
                identity.capabilities -= coordinator.revoked_capabilities.get(identity.id, set())
                return identity

    coordinator = Coordinator(True)
    coordinator.revoked_capabilities = {}
    monkeypatch.setattr("labgrid.remote.coordinator.ClientIdentity", RevocableClientIdentity)
    server = grpc.aio.server()
    labgrid_coordinator_pb2_grpc.add_CoordinatorServicer_to_server(coordinator, server)
    server.add_insecure_port("[::]:20408")
    await server.start()
    yield coordinator
    await server.stop(5)

@pytest_asyncio.fixture(loop_scope='function')
async def async_coordinator_no_capabilities(monkeypatch):
    coordinator = Coordinator(False)
    server = grpc.aio.server()
    labgrid_coordinator_pb2_grpc.add_CoordinatorServicer_to_server(coordinator, server)
    server.add_insecure_port("[::]:20408")
    await server.start()
    yield coordinator
    await server.stop(5)

@pytest_asyncio.fixture(loop_scope='function')
async def client():
    loop = asyncio.get_running_loop()
    client = ClientSession("127.0.0.1:20408", loop=loop)
    await client.start()
    yield client
    await client.stop()

class OtherClientSession(ClientSession):
    def getuser(self):
        return "otheruser"

@pytest_asyncio.fixture(loop_scope='function')
async def other_client():
    loop = asyncio.get_running_loop()
    client = OtherClientSession("127.0.0.2:20408", loop=loop)
    await client.start()
    yield client
    await client.stop()

@pytest_asyncio.fixture(loop_scope='function')
async def anonymous_stub():
    channel = grpc.aio.insecure_channel("127.0.0.1:20408")
    yield labgrid_coordinator_pb2_grpc.CoordinatorStub(channel)
    await channel.close()

@pytest_asyncio.fixture(loop_scope='function')
async def exporter_stub():
    identity = IdentityClientStreamStreamInterceptor(
        username="exporter", hostname="exporterhost", user_agent="labgrid-exporter test"
    )
    channel = grpc.aio.insecure_channel("127.0.0.1:20408", interceptors=[identity])
    yield labgrid_coordinator_pb2_grpc.CoordinatorStub(channel)
    await channel.close()

async def exporter_messages():
    await asyncio.Event().wait()
    yield

def client_id(client):
    return f"{client.gethostname()}/{client.getuser()}"

async def assert_rpc_error(call, code):
    with pytest.raises(grpc.aio.AioRpcError) as excinfo:
        await call
    assert excinfo.value.code() == code, excinfo.value.details()
    return excinfo.value

async def acquire_testplace(client):
    args = argparse.Namespace()
    args.place = "testplace"
    args.allow_unmatched = False
    client.args = args
    await client.add_place()
    await client.acquire()

async def reserve_testplace(client):
    args = argparse.Namespace()
    args.prio = 10
    args.shell = False
    args.wait = False
    args.filters = ["name=testplace"]
    client.args = args
    return await client.create_reservation()

@pytest.mark.asyncio
async def test_cap_add_place(async_coordinator, client):
    args = argparse.Namespace()
    args.place = "testplace"
    args.allow_unmatched = False
    client.args = args
    await client.add_place()
    place = client.get_place("testplace")
    assert place is not None

@pytest.mark.asyncio
async def test_cap_acquire_place(async_coordinator, client):
    args = argparse.Namespace()
    args.place = "testplace"
    args.allow_unmatched = False
    client.args = args
    await client.add_place()

    await client.acquire()
    place = client.get_place("testplace")
    assert place.acquired is not None

@pytest.mark.asyncio
async def test_cap_release_place(async_coordinator, client):
    args = argparse.Namespace()
    args.place = "testplace"
    args.allow_unmatched = False
    client.args = args
    await client.add_place()

    await client.acquire()
    place = client.get_place("testplace")
    assert place.acquired is not None

    await client.release()
    place = client.get_place("testplace")
    assert place.acquired is None

@pytest.mark.asyncio
async def test_cap_delete_place(async_coordinator, client):
    args = argparse.Namespace()
    args.place = "testplace"
    args.allow_unmatched = False
    client.args = args
    await client.add_place()

    await client.del_place()

@pytest.mark.asyncio
async def test_cap_add_place_alias(async_coordinator, client):
    args = argparse.Namespace()
    args.place = "testplace"
    args.allow_unmatched = False
    args.alias = "testalias"
    client.args = args
    await client.add_place()

    await client.add_alias()

@pytest.mark.asyncio
async def test_cap_del_place_alias(async_coordinator, client):
    args = argparse.Namespace()
    args.place = "testplace"
    args.allow_unmatched = False
    args.alias = "testalias"
    client.args = args
    await client.add_place()

    await client.add_alias()

    await client.del_alias()

@pytest.mark.asyncio
async def test_cap_add_place_match(async_coordinator, client):
    args = argparse.Namespace()
    args.place = "testplace"
    args.allow_unmatched = False
    args.patterns = [ "my/test/pattern/" ]
    client.args = args
    await client.add_place()

    await client.add_match()

    place = client.get_place("testplace")
    assert place.matches is not None, place.matches

@pytest.mark.asyncio
async def test_cap_del_place_match(async_coordinator, client):
    args = argparse.Namespace()
    args.place = "testplace"
    args.allow_unmatched = False
    args.patterns = [ "my/test/pattern/" ]
    client.args = args
    await client.add_place()

    await client.add_match()

    place = client.get_place("testplace")
    assert place.matches is not None, place.matches

    await client.del_match()
    place = client.get_place("testplace")
    assert len(place.matches) == 0, place.matches

@pytest.mark.asyncio
async def test_cap_create_reservation(async_coordinator, client):
    args = argparse.Namespace()
    args.place = "testplace"
    args.user = "testhost/testuser"
    args.prio = 10
    args.shell = False
    args.wait = False
    client.args = args
    args.filters = ["name=someplace"]
    await client.add_place()

    await client.create_reservation()

@pytest.mark.asyncio
async def test_cap_cancel_reservation(async_coordinator, client):
    args = argparse.Namespace()
    args.place = "testplace"
    args.user = "testhost/testuser"
    args.prio = 10
    args.shell = False
    args.wait = False
    client.args = args
    args.filters = ["name=someplace"]
    await client.add_place()

    res_id = await client.create_reservation()

    client.args.reservation_id = res_id

    await client.cancel_reservation()

@pytest.mark.asyncio
async def test_cap_print_reservation(async_coordinator, client):
    args = argparse.Namespace()
    args.place = "testplace"
    args.user = "testhost/testuser"
    args.prio = 10
    args.shell = False
    args.wait = False
    client.args = args
    args.filters = ["name=someplace"]
    await client.add_place()

    await client.create_reservation()

    await client.print_reservations()

def test_cap_identity_has_all_capabilities():
    metadata = (("x-lg-hostname", "testhost"), ("x-lg-name", "testuser"))
    identity = ClientIdentity.from_metadata(metadata)
    assert identity.capabilities == set(Capability)

@pytest.mark.asyncio
async def test_cap_set_place_tags(async_coordinator, client):
    args = argparse.Namespace()
    args.place = "testplace"
    args.allow_unmatched = False
    args.tags = ["board=testboard"]
    client.args = args
    await client.add_place()

    await client.set_tags()

    place = client.get_place("testplace")
    assert place.tags == {"board": "testboard"}

@pytest.mark.asyncio
async def test_cap_set_place_comment(async_coordinator, client):
    args = argparse.Namespace()
    args.place = "testplace"
    args.allow_unmatched = False
    args.comment = ["test", "comment"]
    client.args = args
    await client.add_place()

    await client.set_comment()

    place = client.get_place("testplace")
    assert place.comment == "test comment"

@pytest.mark.asyncio
async def test_cap_get_places(async_coordinator, client):
    args = argparse.Namespace()
    args.place = "testplace"
    args.allow_unmatched = False
    client.args = args
    await client.add_place()

    request = labgrid_coordinator_pb2.GetPlacesRequest()
    response = await client.stub.GetPlaces(request)

    assert [place.name for place in response.places] == ["testplace"]

@pytest.mark.asyncio
async def test_cap_poll_reservation(async_coordinator, client):
    args = argparse.Namespace()
    args.prio = 10
    args.shell = False
    args.wait = False
    args.filters = ["name=testplace"]
    client.args = args
    res_id = await client.create_reservation()

    request = labgrid_coordinator_pb2.PollReservationRequest(token=res_id)
    response = await client.stub.PollReservation(request)

    assert response.reservation.token == res_id

@pytest.mark.asyncio
async def test_cap_allow_place(async_coordinator, client):
    args = argparse.Namespace()
    args.place = "testplace"
    args.allow_unmatched = False
    args.user = "otherhost/otheruser"
    client.args = args
    await client.add_place()
    await client.acquire()

    await client.allow()

    place = client.get_place("testplace")
    assert "otherhost/otheruser" in place.allowed

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,capability",
    [
        ("AddPlace", Capability.add_place),
        ("DeletePlace", Capability.delete_place),
        ("AddPlaceAlias", Capability.add_place_alias),
        ("DeletePlaceAlias", Capability.delete_place_alias),
        ("SetPlaceTags", Capability.set_place_tags),
        ("SetPlaceComment", Capability.set_place_comment),
        ("AddPlaceMatch", Capability.add_place_match),
        ("DeletePlaceMatch", Capability.delete_place_match),
        ("AcquirePlace", Capability.acquire_place),
        ("GetPlaces", Capability.get_places),
        ("CreateReservation", Capability.create_reservation),
        ("PollReservation", Capability.poll_reservation),
        ("GetReservations", Capability.get_reservations),
    ],
)
async def test_cap_missing_capability(async_coordinator, client, method, capability):
    revoke_capabilities(async_coordinator, client_id(client), capability)

    request = getattr(labgrid_coordinator_pb2, f"{method}Request")()
    call = getattr(client.stub, method)(request)

    error = await assert_rpc_error(call, grpc.StatusCode.PERMISSION_DENIED)
    assert capability in error.details()

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method",
    [
        "AddPlace",
        "DeletePlace",
        "AddPlaceAlias",
        "DeletePlaceAlias",
        "SetPlaceTags",
        "SetPlaceComment",
        "AddPlaceMatch",
        "DeletePlaceMatch",
        "AcquirePlace",
        "ReleasePlace",
        "GetPlaces",
        "CreateReservation",
        "PollReservation",
        "GetReservations",
    ],
)
async def test_cap_unauthenticated(async_coordinator, anonymous_stub, method):
    request = getattr(labgrid_coordinator_pb2, f"{method}Request")()
    call = getattr(anonymous_stub, method)(request)

    await assert_rpc_error(call, grpc.StatusCode.UNAUTHENTICATED)

@pytest.mark.asyncio
async def test_cap_client_stream_missing_capability(async_coordinator):
    loop = asyncio.get_running_loop()
    client = ClientSession("127.0.0.1:20408", loop=loop)
    revoke_capabilities(async_coordinator, client_id(client), Capability.client_stream)

    try:
        with pytest.raises(ServerError):
            await client.start()
    finally:
        await client.stop()

    assert not async_coordinator.clients

@pytest.mark.asyncio
async def test_cap_client_stream_unauthenticated(async_coordinator, anonymous_stub):
    msg = labgrid_coordinator_pb2.ClientInMessage()
    msg.startup.version = "2.0.0"
    msg.startup.name = "testhost/testuser"
    stream = anonymous_stub.ClientStream(iter([msg]))

    await assert_rpc_error(asyncio.wait_for(stream.read(), timeout=5), grpc.StatusCode.UNAUTHENTICATED)

    assert not async_coordinator.clients

@pytest.mark.asyncio
async def test_cap_exporter_stream(async_coordinator, exporter_stub):
    stream = exporter_stub.ExporterStream(exporter_messages())

    try:
        msg = await asyncio.wait_for(stream.read(), timeout=5)
        assert msg.WhichOneof("kind") == "hello"

        # the exporter session is registered after the hello message
        async with asyncio.timeout(5):
            while not async_coordinator.exporters:
                await asyncio.sleep(0.01)
    finally:
        stream.cancel()

    [exporter] = async_coordinator.exporters.values()
    assert exporter.name == "exporterhost/exporter"

@pytest.mark.asyncio
async def test_cap_exporter_stream_missing_capability(async_coordinator, exporter_stub):
    revoke_capabilities(async_coordinator, "exporterhost/exporter", Capability.exporter_stream)
    stream = exporter_stub.ExporterStream(exporter_messages())

    try:
        call = asyncio.wait_for(stream.read(), timeout=5)
        error = await assert_rpc_error(call, grpc.StatusCode.PERMISSION_DENIED)
    finally:
        stream.cancel()

    assert Capability.exporter_stream in error.details()
    assert not async_coordinator.exporters

@pytest.mark.asyncio
async def test_cap_exporter_stream_unauthenticated(async_coordinator, anonymous_stub):
    stream = anonymous_stub.ExporterStream(exporter_messages())

    try:
        call = asyncio.wait_for(stream.read(), timeout=5)
        await assert_rpc_error(call, grpc.StatusCode.UNAUTHENTICATED)
    finally:
        stream.cancel()

    assert not async_coordinator.exporters

@pytest.mark.asyncio
async def test_cap_release_place_owned_missing_capability(async_coordinator, client):
    await acquire_testplace(client)
    revoke_capabilities(async_coordinator, client_id(client), Capability.release_place_owned, Capability.release_place_any)

    request = labgrid_coordinator_pb2.ReleasePlaceRequest(placename="testplace")
    error = await assert_rpc_error(client.stub.ReleasePlace(request), grpc.StatusCode.PERMISSION_DENIED)

    assert Capability.release_place_owned in error.details()
    assert async_coordinator.places["testplace"].acquired == client_id(client)

@pytest.mark.asyncio
async def test_cap_release_place_owned_with_any_capability(async_coordinator, client):
    await acquire_testplace(client)
    revoke_capabilities(async_coordinator, client_id(client), Capability.release_place_owned)

    await client.release()

    place = client.get_place("testplace")
    assert place.acquired is None

@pytest.mark.asyncio
async def test_cap_release_place_other_missing_capability(async_coordinator, client, other_client):
    await acquire_testplace(client)
    revoke_capabilities(async_coordinator, client_id(other_client), Capability.release_place_any)

    request = labgrid_coordinator_pb2.ReleasePlaceRequest(placename="testplace")
    error = await assert_rpc_error(other_client.stub.ReleasePlace(request), grpc.StatusCode.PERMISSION_DENIED)

    assert Capability.release_place_any in error.details()
    assert async_coordinator.places["testplace"].acquired == client_id(client)

@pytest.mark.asyncio
async def test_cap_release_place_other(async_coordinator, client, other_client):
    await acquire_testplace(client)

    args = argparse.Namespace()
    args.place = "testplace"
    args.kick = True
    other_client.args = args
    await other_client.release()

    place = other_client.get_place("testplace")
    assert place.acquired is None

@pytest.mark.asyncio
async def test_cap_release_place_fromuser_missing_capability(async_coordinator, client, other_client):
    await acquire_testplace(client)
    revoke_capabilities(async_coordinator, client_id(other_client), Capability.release_place_any)

    request = labgrid_coordinator_pb2.ReleasePlaceRequest(placename="testplace", fromuser=client_id(client))
    error = await assert_rpc_error(other_client.stub.ReleasePlace(request), grpc.StatusCode.PERMISSION_DENIED)

    assert Capability.release_place_any in error.details()
    assert async_coordinator.places["testplace"].acquired == client_id(client)

@pytest.mark.asyncio
async def test_cap_release_place_fromuser(async_coordinator, client, other_client):
    await acquire_testplace(client)

    args = argparse.Namespace()
    args.place = "testplace"
    args.acquired = client_id(client)
    other_client.args = args
    await other_client.release_from()

    place = other_client.get_place("testplace")
    assert place.acquired is None

@pytest.mark.asyncio
async def test_cap_allow_place_owned_missing_capability(async_coordinator, client):
    await acquire_testplace(client)
    revoke_capabilities(async_coordinator, client_id(client), Capability.allow_place_owned, Capability.allow_place_any)

    request = labgrid_coordinator_pb2.AllowPlaceRequest(placename="testplace", user="otherhost/otheruser")
    error = await assert_rpc_error(client.stub.AllowPlace(request), grpc.StatusCode.PERMISSION_DENIED)

    assert Capability.allow_place_owned in error.details()
    assert "otherhost/otheruser" not in async_coordinator.places["testplace"].allowed

@pytest.mark.asyncio
async def test_cap_allow_place_owned_with_any_capability(async_coordinator, client):
    await acquire_testplace(client)
    revoke_capabilities(async_coordinator, client_id(client), Capability.allow_place_owned)

    client.args.user = "otherhost/otheruser"
    await client.allow()

    place = client.get_place("testplace")
    assert "otherhost/otheruser" in place.allowed

@pytest.mark.asyncio
async def test_cap_allow_place_other_missing_capability(async_coordinator, client, other_client):
    await acquire_testplace(client)
    revoke_capabilities(async_coordinator, client_id(other_client), Capability.allow_place_any)

    request = labgrid_coordinator_pb2.AllowPlaceRequest(placename="testplace", user=client_id(other_client))
    error = await assert_rpc_error(other_client.stub.AllowPlace(request), grpc.StatusCode.PERMISSION_DENIED)

    assert Capability.allow_place_any in error.details()
    assert client_id(other_client) not in async_coordinator.places["testplace"].allowed

@pytest.mark.asyncio
async def test_cap_allow_place_other(async_coordinator, client, other_client):
    await acquire_testplace(client)

    # ClientSession.allow() refuses places not acquired by the client itself
    request = labgrid_coordinator_pb2.AllowPlaceRequest(placename="testplace", user=client_id(other_client))
    await other_client.stub.AllowPlace(request)
    await other_client.sync_with_coordinator()

    place = other_client.get_place("testplace")
    assert client_id(other_client) in place.allowed

@pytest.mark.asyncio
async def test_cap_cancel_reservation_owned_missing_capability(async_coordinator, client):
    res_id = await reserve_testplace(client)
    revoke_capabilities(
        async_coordinator, client_id(client), Capability.cancel_reservation_owned, Capability.cancel_reservation_any
    )

    request = labgrid_coordinator_pb2.CancelReservationRequest(token=res_id)
    await assert_rpc_error(client.stub.CancelReservation(request), grpc.StatusCode.PERMISSION_DENIED)

    assert res_id in async_coordinator.reservations

@pytest.mark.asyncio
async def test_cap_cancel_reservation_owned_with_any_capability(async_coordinator, client):
    res_id = await reserve_testplace(client)
    revoke_capabilities(async_coordinator, client_id(client), Capability.cancel_reservation_owned)

    client.args.reservation_id = res_id
    await client.cancel_reservation()

    assert res_id not in async_coordinator.reservations

@pytest.mark.asyncio
async def test_cap_cancel_reservation_other_missing_capability(async_coordinator, client, other_client):
    res_id = await reserve_testplace(client)
    revoke_capabilities(async_coordinator, client_id(other_client), Capability.cancel_reservation_any)

    request = labgrid_coordinator_pb2.CancelReservationRequest(token=res_id)
    error = await assert_rpc_error(other_client.stub.CancelReservation(request), grpc.StatusCode.PERMISSION_DENIED)

    assert Capability.cancel_reservation_any in error.details()
    assert res_id in async_coordinator.reservations

@pytest.mark.asyncio
async def test_cap_cancel_reservation_other(async_coordinator, client, other_client):
    res_id = await reserve_testplace(client)

    args = argparse.Namespace()
    args.reservation_id = res_id
    other_client.args = args
    await other_client.cancel_reservation()

    assert res_id not in async_coordinator.reservations

@pytest.mark.asyncio
async def test_nocap_unauthenticated(async_coordinator_no_capabilities, anonymous_stub):
    request = labgrid_coordinator_pb2.AddPlaceRequest(name="testplace")
    await anonymous_stub.AddPlace(request)

    assert "testplace" in async_coordinator_no_capabilities.places

@pytest.mark.asyncio
async def test_nocap_ignores_capabilities(async_coordinator_no_capabilities, client):
    await acquire_testplace(client)
    await client.release()

    place = client.get_place("testplace")
    assert place.acquired is None

@pytest.mark.asyncio
async def test_nocap_allow_place_other(async_coordinator_no_capabilities, client, other_client):
    await acquire_testplace(client)

    request = labgrid_coordinator_pb2.AllowPlaceRequest(placename="testplace", user=client_id(other_client))
    await assert_rpc_error(other_client.stub.AllowPlace(request), grpc.StatusCode.FAILED_PRECONDITION)

    assert client_id(other_client) not in async_coordinator_no_capabilities.places["testplace"].allowed

@pytest.mark.asyncio
async def test_nocap_release_place_no_session(async_coordinator_no_capabilities, client, anonymous_stub):
    await acquire_testplace(client)

    request = labgrid_coordinator_pb2.ReleasePlaceRequest(placename="testplace")
    await assert_rpc_error(anonymous_stub.ReleasePlace(request), grpc.StatusCode.FAILED_PRECONDITION)

    assert async_coordinator_no_capabilities.places["testplace"].acquired == client_id(client)

@pytest.mark.asyncio
async def test_nocap_cancel_reservation_no_session(async_coordinator_no_capabilities, client, anonymous_stub):
    token = await reserve_testplace(client)

    request = labgrid_coordinator_pb2.CancelReservationRequest(token=token)
    await assert_rpc_error(anonymous_stub.CancelReservation(request), grpc.StatusCode.FAILED_PRECONDITION)

    assert token in async_coordinator_no_capabilities.reservations
