import asyncio
import os
import signal
from types import SimpleNamespace

import grpc
import pexpect
import pytest
import labgrid.remote.generated.labgrid_coordinator_pb2_grpc as labgrid_coordinator_pb2_grpc
import labgrid.remote.generated.labgrid_coordinator_pb2 as labgrid_coordinator_pb2
from labgrid.remote.common import Place
from labgrid.remote.coordinator import Coordinator, ExporterError, ResourceImport


class FakeExporterCommandQueue:
    def __init__(self, *, success, reason="release failed", on_command=None):
        self.success = success
        self.reason = reason
        self.on_command = on_command

    def put_nowait(self, command):
        if self.on_command:
            self.on_command(command)
        response = labgrid_coordinator_pb2.ExporterResponse(success=self.success)
        if not self.success:
            response.reason = self.reason
        command.complete(response)


def make_coordinator_with_fake_exporter(
    *,
    release_success,
    release_reason="release failed",
    on_release_command=None,
):
    coordinator = Coordinator.__new__(Coordinator)
    coordinator.use_capabilities = False;
    coordinator.lock = asyncio.Lock()
    coordinator.clients = {
        "unknown-peer" : SimpleNamespace(
            name="testhost",
            ),
    }
    coordinator.exporters = {
        "peer": SimpleNamespace(
            name="testhost",
            queue=FakeExporterCommandQueue(
                success=release_success,
                reason=release_reason,
                on_command=on_release_command,
            ),
        )
    }
    return coordinator


def make_place_with_acquired_resource():
    place = Place("test")
    place.acquired = "testclient"
    resource = ResourceImport(
        data={
            "cls": "NetworkSerialPort",
            "params": {},
            "acquired": place.name,
            "avail": True,
        },
        path=("testhost", "Testport", "NetworkSerialPort", "NetworkSerialPort"),
    )
    place.acquired_resources.append(resource)
    return place, resource


@pytest.fixture(scope="function")
def channel_stub():
    import queue

    queue = queue.Queue()

    channel = grpc.insecure_channel("127.0.0.1:20408")
    stub = labgrid_coordinator_pb2_grpc.CoordinatorStub(channel)

    def generate_startup(queue):
        msg = labgrid_coordinator_pb2.ClientInMessage()
        msg.startup.version = "2.0.0"
        msg.startup.name = "testclient"
        messages = [msg]
        for msg in messages:
            yield msg
        while True:
            msg = queue.get()
            yield msg
            queue.task_done()

    stream = stub.ClientStream(generate_startup(queue))
    yield stub
    channel.close()


@pytest.fixture(scope="function")
def coordinator_place(channel_stub):
    name = "test"
    place = labgrid_coordinator_pb2.AddPlaceRequest(name=name)
    res = channel_stub.AddPlace(place)
    assert res, f"There was an error: {res}"
    return channel_stub


def test_startup(coordinator):
    pass


def test_coordinator_add_place(coordinator, channel_stub):
    name = "test"
    place = labgrid_coordinator_pb2.AddPlaceRequest(name=name)
    res = channel_stub.AddPlace(place)
    assert res, f"There was an error: {res}"


def test_coordinator_del_place(coordinator, channel_stub):
    name = "test"
    place = labgrid_coordinator_pb2.AddPlaceRequest(name=name)
    res = channel_stub.AddPlace(place)
    assert res, f"There was an error: {res}"
    place = labgrid_coordinator_pb2.DeletePlaceRequest(name=name)
    res = channel_stub.DeletePlace(place)
    assert res, f"There was an error: {res}"


def test_coordinator_get_places(coordinator, channel_stub):
    name = "test"
    place = labgrid_coordinator_pb2.AddPlaceRequest(name=name)
    res = channel_stub.AddPlace(place)
    assert res, f"There was an error: {res}"
    name = "test2"
    place = labgrid_coordinator_pb2.AddPlaceRequest(name=name)
    res = channel_stub.AddPlace(place)
    assert res, f"There was an error: {res}"

    request = labgrid_coordinator_pb2.GetPlacesRequest()
    res = channel_stub.GetPlaces(request)

    from labgrid.remote.common import Place

    places = set()
    names = set()
    for pb2 in res.places:
        place = Place.from_pb2(pb2)
        places.add(place)
        names.add(place.name)

    assert len(places) == 2, f"Returned places not two: {places}"
    assert set(names) == {"test", "test2"}, f"There was an error: {res}"


def test_coordinator_exporter_session(coordinator, channel_stub):
    import queue

    queue = queue.Queue()

    def generate_startup(queue):
        msg = labgrid_coordinator_pb2.ExporterInMessage()
        msg.startup.version = "2.0.0"
        msg.startup.name = "testporter"
        messages = [msg]
        for msg in messages:
            yield msg
        while True:
            msg = queue.get()
            yield msg
            queue.task_done()

    coordinator = channel_stub.ExporterStream(generate_startup(queue), wait_for_ready=True)


def test_cleanup_exporter_ignores_request_task_error():
    async def run():
        coordinator = object.__new__(Coordinator)
        removed = []
        coordinator.exporters = {
            "peer": SimpleNamespace(
                groups={"group": {"resource": object()}},
                set_resource=lambda *args: removed.append(args),
            ),
        }

        async def request_task():
            raise RuntimeError("request task failed")

        task = asyncio.create_task(request_task())
        await asyncio.sleep(0)
        await coordinator._cleanup_exporter("peer", task)

        assert "peer" not in coordinator.exporters
        assert removed == [("group", "resource", None)]

    asyncio.run(run())


def test_coordinator_place_acquire(coordinator, coordinator_place):
    stub = coordinator_place
    res = stub.AcquirePlace(labgrid_coordinator_pb2.AcquirePlaceRequest(placename="test"))
    assert res


def test_coordinator_place_acquire_release(coordinator, coordinator_place):
    stub = coordinator_place
    res = stub.AcquirePlace(labgrid_coordinator_pb2.AcquirePlaceRequest(placename="test"))
    assert res
    res = stub.ReleasePlace(labgrid_coordinator_pb2.ReleasePlaceRequest(placename="test"))
    assert res


def test_coordinator_release_resources_removes_resource_on_success():
    coordinator = make_coordinator_with_fake_exporter(release_success=True)
    place, resource = make_place_with_acquired_resource()

    async def release_resources():
        async with coordinator.lock:
            await coordinator._release_resources(place, [resource])

    asyncio.run(release_resources())

    assert resource not in place.acquired_resources


def test_coordinator_release_resources_keeps_resource_on_exporter_failure():
    coordinator = make_coordinator_with_fake_exporter(release_success=False)
    place, resource = make_place_with_acquired_resource()

    async def release_resources():
        async with coordinator.lock:
            await coordinator._release_resources(place, [resource])

    with pytest.raises(ExporterError, match="release failed"):
        asyncio.run(release_resources())

    assert resource in place.acquired_resources


def test_coordinator_place_add_alias(coordinator, coordinator_place):
    stub = coordinator_place
    res = stub.AddPlaceAlias(labgrid_coordinator_pb2.AddPlaceAliasRequest(placename="test", alias="testalias"))
    assert res


def test_coordinator_place_add_remove_alias(coordinator, coordinator_place):
    stub = coordinator_place
    res = stub.AddPlaceAlias(labgrid_coordinator_pb2.AddPlaceAliasRequest(placename="test", alias="testalias"))
    assert res
    res = stub.DeletePlaceAlias(labgrid_coordinator_pb2.DeletePlaceAliasRequest(placename="test", alias="testalias"))
    assert res


def test_coordinator_place_set_tags(coordinator, coordinator_place):
    stub = coordinator_place
    res = stub.SetPlaceTags(labgrid_coordinator_pb2.SetPlaceTagsRequest(placename="test", tags={"one": "two"}))
    assert res


def test_coordinator_place_set_comment(coordinator, coordinator_place):
    stub = coordinator_place
    res = stub.SetPlaceComment(labgrid_coordinator_pb2.SetPlaceCommentRequest(placename="test", comment="testcomment"))
    assert res


def test_coordinator_place_add_match(coordinator, coordinator_place):
    stub = coordinator_place
    res = stub.AddPlaceMatch(
        labgrid_coordinator_pb2.AddPlaceMatchRequest(placename="test", pattern="this/test/pattern")
    )
    assert res


def test_coordinator_place_add_delete_match(coordinator, coordinator_place):
    stub = coordinator_place
    res = stub.AddPlaceMatch(
        labgrid_coordinator_pb2.AddPlaceMatchRequest(placename="test", pattern="this/test/pattern")
    )
    assert res
    res = stub.DeletePlaceMatch(
        labgrid_coordinator_pb2.DeletePlaceMatchRequest(placename="test", pattern="this/test/pattern")
    )
    assert res


def test_coordinator_place_allow(coordinator, coordinator_place):
    stub = coordinator_place
    res = stub.AcquirePlace(labgrid_coordinator_pb2.AcquirePlaceRequest(placename="test"))
    assert res
    res = stub.AllowPlace(labgrid_coordinator_pb2.AllowPlaceRequest(placename="test", user="othertest"))
    assert res


def test_coordinator_create_reservation(coordinator, coordinator_place):
    tags = {"board": "test"}
    stub = coordinator_place
    res = stub.SetPlaceTags(labgrid_coordinator_pb2.SetPlaceTagsRequest(placename="test", tags=tags))
    assert res
    res = stub.CreateReservation(
        labgrid_coordinator_pb2.CreateReservationRequest(
            filters={
                "main": labgrid_coordinator_pb2.Reservation.Filter(filter={"board": "test"}),
            },
            prio=1.0,
        )
    )
    assert res
    res: labgrid_coordinator_pb2.CreateReservationResponse
    assert len(res.reservation.token) > 0


def test_coordinator_propagate_identity_on_lock_and_release(coordinator, channel_stub, tmpdir):
    with open(tmpdir / "exports.yaml", "w") as f:
        f.write(
            """
        Example:
            NetworkService:
              address: "192.168.0.1"
              username: "root"
        """
        )

    stub = channel_stub

    assert stub.AddPlace(labgrid_coordinator_pb2.AddPlaceRequest(name="place1"))
    assert stub.AddPlaceMatch(
        labgrid_coordinator_pb2.AddPlaceMatchRequest(
            placename="place1", pattern="testexporter/Example/NetworkService"
        )
    )

    with pexpect.spawn("python -m labgrid.remote.exporter --name testexporter exports.yaml", cwd=tmpdir) as spawn:
        spawn.expect("Exporter ready")

        with pexpect.spawn(
            "python -m labgrid.remote.client -p place1 lock",
            cwd=tmpdir,
            env=os.environ | {"LG_HOSTNAME": "somehost", "LG_USERNAME": "someuser"},
        ) as spawn_acquire:
            spawn_acquire.expect("acquired place place1")
            spawn_acquire.expect(pexpect.EOF)

        spawn.expect("INFO:root:Example/NetworkService acquired by somehost/someuser")

        with pexpect.spawn(
            "python -m labgrid.remote.client -p place1 release --kick",
            cwd=tmpdir,
            env=os.environ | {"LG_HOSTNAME": "otherhost", "LG_USERNAME": "otheruser"},
        ) as spawn_release:
            spawn_release.expect("released place place1")
            spawn_release.expect(pexpect.EOF)

        spawn.expect("INFO:root:Example/NetworkService released by otherhost/otheruser")

        spawn.kill(signal.SIGTERM)
        spawn.expect(pexpect.EOF)


@pytest.mark.parametrize(
    "metadata, legacy_name, expected_identity",
    [
        pytest.param(
            (("x-lg-hostname", "releasehost"), ("x-lg-name", "releaser")),
            None,
            "releasehost/releaser",
            id="metadata-without-session",
        ),
        pytest.param(
            (("x-lg-hostname", "releasehost"), ("x-lg-name", "releaser")),
            "legacyhost/legacyuser",
            "releasehost/releaser",
            id="metadata-overrides-session",
        ),
        pytest.param((), "legacyhost/legacyuser", "legacyhost/legacyuser", id="legacy-session"),
    ],
)
@pytest.mark.parametrize("release_success", [True, False], ids=["success", "exporter-failure"])
def test_coordinator_propagate_release_identity(
    mocker, metadata, legacy_name, expected_identity, release_success
):
    place, resource = make_place_with_acquired_resource()
    owner = place.acquired
    requests = []

    def on_release(command):
        requests.append(command.request)
        if release_success:
            resource.data["acquired"] = None

    coordinator = make_coordinator_with_fake_exporter(
        release_success=release_success, on_release_command=on_release
    )
    coordinator.places = {place.name: place}
    coordinator._publish_place = mocker.Mock()
    coordinator._publish_resource = mocker.Mock()
    coordinator.save_later = mocker.Mock()
    coordinator.schedule_reservations = mocker.Mock()
    if legacy_name:
        coordinator.clients["client-peer"] = SimpleNamespace(name=legacy_name)
    context = SimpleNamespace(
        invocation_metadata=lambda: metadata,
        peer=lambda: "client-peer",
        abort=mocker.AsyncMock(side_effect=RuntimeError("RPC aborted")),
    )
    request = labgrid_coordinator_pb2.ReleasePlaceRequest(placename=place.name)

    if release_success:
        response = asyncio.run(coordinator.ReleasePlace(request, context))
        assert isinstance(response, labgrid_coordinator_pb2.ReleasePlaceResponse)
        context.abort.assert_not_awaited()
        assert place.acquired is None
        assert not place.acquired_resources
        coordinator.schedule_reservations.assert_called_once_with()
    else:
        with pytest.raises(RuntimeError, match="RPC aborted"):
            asyncio.run(coordinator.ReleasePlace(request, context))
        context.abort.assert_awaited_once_with(
            grpc.StatusCode.FAILED_PRECONDITION,
            f"Failed to release resources for place {place.name}: release failed",
        )
        assert place.acquired == owner
        assert place.acquired_resources == [resource]
        coordinator.schedule_reservations.assert_not_called()
        coordinator._publish_resource.assert_called_once_with(resource)

    assert len(requests) == 1
    assert requests[0].client_identity.id == expected_identity
    assert requests[0].client_identity.id != owner
    assert not requests[0].HasField("place_name")
    coordinator._publish_place.assert_called_once_with(place)
    coordinator.save_later.assert_called_once_with()


def test_coordinator_cleanup_release_has_empty_identity():
    requests = []
    coordinator = make_coordinator_with_fake_exporter(
        release_success=True, on_release_command=lambda command: requests.append(command.request)
    )
    place, resource = make_place_with_acquired_resource()

    async def release_resources():
        async with coordinator.lock:
            await coordinator._release_resources(place, [resource])

    asyncio.run(release_resources())

    assert len(requests) == 1
    assert requests[0].client_identity.id == ""
    assert not requests[0].HasField("place_name")


@pytest.mark.parametrize("acquired", [None, "original-owner"], ids=["already-free", "different-owner"])
def test_coordinator_release_fromuser_noop_without_identity(mocker, acquired):
    on_release = mocker.Mock()
    coordinator = make_coordinator_with_fake_exporter(
        release_success=True, on_release_command=on_release
    )
    place, resource = make_place_with_acquired_resource()
    place.acquired = acquired
    coordinator.places = {place.name: place}
    context = SimpleNamespace(
        invocation_metadata=lambda: (),
        peer=lambda: "unknown-peer",
        abort=mocker.AsyncMock(side_effect=RuntimeError("RPC aborted")),
    )
    request = labgrid_coordinator_pb2.ReleasePlaceRequest(
        placename=place.name, fromuser="another-owner"
    )

    response = asyncio.run(coordinator.ReleasePlace(request, context))

    assert isinstance(response, labgrid_coordinator_pb2.ReleasePlaceResponse)
    assert place.acquired == acquired
    assert place.acquired_resources == [resource]
    on_release.assert_not_called()
    context.abort.assert_not_awaited()

def test_coordinator_capabilities(coordinator_with_capabilities):
    channel = grpc.insecure_channel("127.0.0.1:20408")
    stub = labgrid_coordinator_pb2_grpc.CoordinatorStub(channel)
    request = labgrid_coordinator_pb2.AddPlaceRequest(name="test")

    with pytest.raises(grpc.RpcError) as excinfo:
        stub.AddPlace(request)
    assert excinfo.value.code() == grpc.StatusCode.UNAUTHENTICATED

    metadata = (("x-lg-hostname", "testhost"), ("x-lg-name", "testuser"))
    res = stub.AddPlace(request, metadata=metadata)
    assert res, f"There was an error: {res}"

    channel.close()
