import asyncio
import os
import signal
import time
from time import monotonic, sleep
from types import SimpleNamespace

import grpc
import pexpect
import pytest
from grpc_health.v1 import health, health_pb2, health_pb2_grpc
from grpc_reflection.v1alpha import reflection_pb2, reflection_pb2_grpc

import labgrid.remote.generated.labgrid_coordinator_pb2 as labgrid_coordinator_pb2
import labgrid.remote.generated.labgrid_coordinator_pb2_grpc as labgrid_coordinator_pb2_grpc
from labgrid.remote.common import Place, Reservation, ReservationState
from labgrid.remote.coordinator import Coordinator, CoordinatorError, ExporterError, ResourceImport


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
    coordinator.lock = asyncio.Lock()
    coordinator.clients = {}
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

LIST_PLACE_RESOURCES_PATTERN = "testhost/ClsNotEqualResourceName/NetworkSerialPort/ExampleResource"


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


@pytest.fixture(scope="function")
def coordinator_reservation(channel_stub):
    res = channel_stub.CreateReservation(
        labgrid_coordinator_pb2.CreateReservationRequest(
            filters={
                "main": labgrid_coordinator_pb2.Reservation.Filter(filter={"board": "test"}),
            },
            prio=1.0,
        )
    )
    assert res, f"There was an error: {res}"
    return res.reservation.token


@pytest.fixture(scope="function")
def health_stub(coordinator):
    with grpc.insecure_channel("127.0.0.1:20408") as channel:
        yield health_pb2_grpc.HealthStub(channel)


def test_startup(coordinator):
    pass


@pytest.mark.parametrize("service_name", ["", "labgrid.Coordinator"])
def test_coordinator_health_check(health_stub, channel_stub, service_name):
    request = health_pb2.HealthCheckRequest(service=service_name)
    assert health_stub.Check(request, timeout=5).status == health_pb2.HealthCheckResponse.SERVING
    # Ordinary RPCs remain available without requiring an exporter or devices.
    channel_stub.AddPlace(labgrid_coordinator_pb2.AddPlaceRequest(name="health-test"), timeout=5)
    assert health_stub.Check(request, timeout=5).status == health_pb2.HealthCheckResponse.SERVING


def test_coordinator_health_check_unknown_service(health_stub):
    with pytest.raises(grpc.RpcError) as excinfo:
        health_stub.Check(health_pb2.HealthCheckRequest(service="missing"), timeout=5)
    assert excinfo.value.code() == grpc.StatusCode.NOT_FOUND


@pytest.mark.parametrize(
    "service_name, expected_status",
    [
        ("", health_pb2.HealthCheckResponse.SERVING),
        ("labgrid.Coordinator", health_pb2.HealthCheckResponse.SERVING),
        ("missing", health_pb2.HealthCheckResponse.SERVICE_UNKNOWN),
    ],
)
def test_coordinator_health_watch(health_stub, service_name, expected_status):
    stream = health_stub.Watch(health_pb2.HealthCheckRequest(service=service_name), timeout=5)
    try:
        assert next(stream).status == expected_status
        assert stream.is_active()
    finally:
        stream.cancel()
    with pytest.raises(grpc.RpcError) as excinfo:
        next(stream)
    assert excinfo.value.code() == grpc.StatusCode.CANCELLED
    assert not stream.is_active()


@pytest.mark.parametrize("service_name", ["", "labgrid.Coordinator"])
def test_coordinator_health_watch_shutdown(coordinator, health_stub, service_name):
    stream = health_stub.Watch(health_pb2.HealthCheckRequest(service=service_name), timeout=10)
    try:
        assert next(stream).status == health_pb2.HealthCheckResponse.SERVING
        coordinator.spawn.kill(signal.SIGTERM)
        assert next(stream).status == health_pb2.HealthCheckResponse.NOT_SERVING
        # Keep the Watch open to exercise the server's bounded grace period.
        with pytest.raises(grpc.RpcError) as excinfo:
            next(stream)
        assert excinfo.value.code() == grpc.StatusCode.UNAVAILABLE
    finally:
        stream.cancel()

    deadline = monotonic() + 5
    while coordinator.isalive() and monotonic() < deadline:
        sleep(0.1)
    assert not coordinator.isalive()
    assert coordinator.exitstatus == 0
    # A stopped server gives a transport error, not a health response.
    with grpc.insecure_channel("127.0.0.1:20408") as channel:
        stub = health_pb2_grpc.HealthStub(channel)
        with pytest.raises(grpc.RpcError) as excinfo:
            stub.Check(health_pb2.HealthCheckRequest(service=service_name), timeout=2)
        assert excinfo.value.code() == grpc.StatusCode.UNAVAILABLE


def test_coordinator_health_reflection(coordinator):
    with grpc.insecure_channel("127.0.0.1:20408") as channel:
        stub = reflection_pb2_grpc.ServerReflectionStub(channel)
        stream = stub.ServerReflectionInfo(iter([reflection_pb2.ServerReflectionRequest(list_services="")]), timeout=5)
        try:
            response = next(stream)
            assert response.HasField("list_services_response")
            services = {service.name for service in response.list_services_response.service}
            assert health.SERVICE_NAME in services
            assert "labgrid.Coordinator" in services
        finally:
            stream.cancel()


def test_coordinator_add_place(coordinator, channel_stub):
    name = "test"
    place = labgrid_coordinator_pb2.AddPlaceRequest(name=name)
    res = channel_stub.AddPlace(place)
    assert res, f"There was an error: {res}"


def test_coordinator_create_place(coordinator, channel_stub):
    name = "test"
    place = labgrid_coordinator_pb2.CreatePlaceRequest(name=name)
    res = channel_stub.CreatePlace(place)
    assert res, f"There was an error: {res}"
    assert res.place.name == name


def test_coordinator_create_place_already_exists(coordinator, channel_stub):
    name = "test"
    place = labgrid_coordinator_pb2.CreatePlaceRequest(name=name)
    res = channel_stub.CreatePlace(place)
    assert res, f"There was an error: {res}"

    with pytest.raises(grpc.RpcError) as excinfo:
        channel_stub.CreatePlace(place)

    assert excinfo.value.code() == grpc.StatusCode.ALREADY_EXISTS
    assert excinfo.value.details() == "Place test already exists"


def test_coordinator_create_place_not_provided(coordinator, channel_stub):
    place = labgrid_coordinator_pb2.CreatePlaceRequest()

    with pytest.raises(grpc.RpcError) as excinfo:
        channel_stub.CreatePlace(place)

    assert excinfo.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert excinfo.value.details() == "name was not a string"


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

    from labgrid.remote.common import Place, Reservation, ReservationState

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
    res = stub.GetPlace(labgrid_coordinator_pb2.GetPlaceRequest(name="test"))
    assert "othertest" in res.place.allowed


def test_coordinator_place_share(coordinator, coordinator_place):
    stub = coordinator_place
    res = stub.AcquirePlace(labgrid_coordinator_pb2.AcquirePlaceRequest(placename="test"))
    assert res
    res = stub.SharePlace(labgrid_coordinator_pb2.SharePlaceRequest(name="test", user="othertest"))
    assert res
    res = stub.GetPlace(labgrid_coordinator_pb2.GetPlaceRequest(name="test"))
    assert "othertest" in res.place.allowed


def test_coordinator_place_share_not_acquired(coordinator, coordinator_place):
    stub = coordinator_place
    with pytest.raises(grpc.RpcError) as excinfo:
        stub.SharePlace(labgrid_coordinator_pb2.SharePlaceRequest(name="test", user="othertest"))

    assert excinfo.value.code() == grpc.StatusCode.FAILED_PRECONDITION
    assert excinfo.value.details() == "Place test is not acquired"


def test_coordinator_place_share_name_not_provided(coordinator, channel_stub):
    request = labgrid_coordinator_pb2.SharePlaceRequest(user="test")

    with pytest.raises(grpc.RpcError) as excinfo:
        channel_stub.SharePlace(request)

    assert excinfo.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert excinfo.value.details() == "name was not a string"


def test_coordinator_place_unshare(coordinator, coordinator_place):
    stub = coordinator_place
    res = stub.AcquirePlace(labgrid_coordinator_pb2.AcquirePlaceRequest(placename="test"))
    assert res
    res = stub.AllowPlace(labgrid_coordinator_pb2.AllowPlaceRequest(placename="test", user="othertest"))
    assert res
    res = stub.UnsharePlace(labgrid_coordinator_pb2.UnsharePlaceRequest(name="test", user="othertest"))
    assert res


def test_coordinator_place_unshare_not_acquired(coordinator, coordinator_place):
    stub = coordinator_place
    request = labgrid_coordinator_pb2.UnsharePlaceRequest(name="test", user="othertest")

    with pytest.raises(grpc.RpcError) as excinfo:
        stub.UnsharePlace(request)

    assert excinfo.value.code() == grpc.StatusCode.FAILED_PRECONDITION
    assert excinfo.value.details() == "Place test is not acquired"


def test_coordinator_place_unshare_not_shared(coordinator, coordinator_place):
    stub = coordinator_place
    res = stub.AcquirePlace(labgrid_coordinator_pb2.AcquirePlaceRequest(placename="test"))
    assert res
    request = labgrid_coordinator_pb2.UnsharePlaceRequest(name="test", user="othertest")

    with pytest.raises(grpc.RpcError) as excinfo:
        stub.UnsharePlace(request)

    assert excinfo.value.code() == grpc.StatusCode.FAILED_PRECONDITION
    assert excinfo.value.details() == "Place test is not shared with othertest"


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
    coordinator.schedule_reservations = mocker.AsyncMock()
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
        coordinator.schedule_reservations.assert_awaited_once_with()
    else:
        with pytest.raises(RuntimeError, match="RPC aborted"):
            asyncio.run(coordinator.ReleasePlace(request, context))
        context.abort.assert_awaited_once_with(
            grpc.StatusCode.FAILED_PRECONDITION,
            f"Failed to release resources for place {place.name}: release failed",
        )
        assert place.acquired == owner
        assert place.acquired_resources == [resource]
        coordinator.schedule_reservations.assert_not_awaited()
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


def test_extend_lease_failure_keeps_single_resource_lease(mocker):
    class AbortError(Exception):
        pass

    client_peer = "test-peer"

    class FakeContext:
        def peer(self):
            return client_peer

        def invocation_metadata(self):
            return ()

        async def abort(self, code, details):
            raise AbortError(details)

    async def run_test():
        coordinator = Coordinator()
        try:
            coordinator.clients[client_peer] = SimpleNamespace(name="testuser")

            now = time.time()
            old_timeout = now + 10
            reservation = Reservation(
                owner="testuser",
                id="reservation-id",
                state=ReservationState.leased,
                timeout=old_timeout,
                lease_start_time=now,
            )
            coordinator.reservations[reservation.id] = reservation

            resource = ResourceImport(
                {
                    "cls": "NetworkSerialPort",
                    "params": {"extra": {}},
                    "acquired": "test",
                    "avail": True,
                },
                path=("testhost", "Testport", "NetworkSerialPort", "NetworkSerialPort"),
            )
            place = Place(
                "test",
                acquired="testuser",
                acquired_resources=[resource],
                reservation=reservation.id,
            )
            coordinator.places[place.name] = place

            mocker.patch.object(
                coordinator,
                "_notify_lease_extended",
                side_effect=ExporterError("extend failed"),
            )

            with pytest.raises(AbortError, match="lease was kept"):
                await coordinator.ExtendLease(
                    labgrid_coordinator_pb2.ExtendLeaseRequest(token=reservation.id),
                    FakeContext(),
                )

            assert reservation.state is ReservationState.leased
            assert reservation.timeout == old_timeout
            assert place.acquired == "testuser"
            assert place.acquired_resources == [resource]
            assert place.reservation == reservation.id
        finally:
            for task in coordinator.poll_tasks:
                task.cancel()
            await asyncio.gather(*coordinator.poll_tasks, return_exceptions=True)

    asyncio.run(run_test())


def test_coordinator_get_place(coordinator, channel_stub):
    name = "test"
    place = labgrid_coordinator_pb2.AddPlaceRequest(name=name)
    res = channel_stub.AddPlace(place)
    assert res, f"There was an error: {res}"

    request = labgrid_coordinator_pb2.GetPlaceRequest(name=name)
    res = channel_stub.GetPlace(request)

    from labgrid.remote.common import Place

    place = Place.from_pb2(res.place)

    assert place.name == name, f"There was an error: {res}"


def test_coordinator_get_place_missing(coordinator, channel_stub):
    request = labgrid_coordinator_pb2.GetPlaceRequest(name="missing")

    with pytest.raises(grpc.RpcError) as excinfo:
        channel_stub.GetPlace(request)

    assert excinfo.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert excinfo.value.details() == "Place missing does not exist"


def test_coordinator_get_place_not_provided(coordinator, channel_stub):
    request = labgrid_coordinator_pb2.GetPlaceRequest()

    with pytest.raises(grpc.RpcError) as excinfo:
        channel_stub.GetPlace(request)

    assert excinfo.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert excinfo.value.details() == "name was not a string"


def test_coordinator_place_unshare_name_not_provided(coordinator, channel_stub):
    request = labgrid_coordinator_pb2.UnsharePlaceRequest(user="test")

    with pytest.raises(grpc.RpcError) as excinfo:
        channel_stub.UnsharePlace(request)

    assert excinfo.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert excinfo.value.details() == "name was not a string"


def test_coordinator_poll_reservation(coordinator, coordinator_place):
    tags = {"board": "test"}
    stub = coordinator_place
    res = stub.SetPlaceTags(labgrid_coordinator_pb2.SetPlaceTagsRequest(placename="test", tags=tags))
    assert res
    res = stub.CreateReservation(
        labgrid_coordinator_pb2.CreateReservationRequest(
            filters={
                "main": labgrid_coordinator_pb2.Reservation.Filter(filter=tags),
            },
            prio=1.0,
        )
    )
    assert res
    token = res.reservation.token
    res = stub.PollReservation(labgrid_coordinator_pb2.PollReservationRequest(token=token))
    assert res
    assert res.reservation.token == token


def test_coordinator_poll_reservation_not_found(coordinator, coordinator_place):
    stub = coordinator_place
    with pytest.raises(grpc.RpcError) as excinfo:
        stub.PollReservation(labgrid_coordinator_pb2.PollReservationRequest(token="nonexistent"))

    assert excinfo.value.code() == grpc.StatusCode.FAILED_PRECONDITION
    assert excinfo.value.details() == "Reservation nonexistent does not exist"


def test_coordinator_refresh_reservation(coordinator, coordinator_place):
    tags = {"board": "test"}
    stub = coordinator_place
    res = stub.SetPlaceTags(labgrid_coordinator_pb2.SetPlaceTagsRequest(placename="test", tags=tags))
    assert res
    res = stub.CreateReservation(
        labgrid_coordinator_pb2.CreateReservationRequest(
            filters={
                "main": labgrid_coordinator_pb2.Reservation.Filter(filter=tags),
            },
            prio=1.0,
        )
    )
    assert res
    token = res.reservation.token
    res = stub.RefreshReservation(labgrid_coordinator_pb2.RefreshReservationRequest(reservation_id=token))
    assert res
    assert res.reservation.token == token


def test_coordinator_refresh_reservation_not_found(coordinator, coordinator_place):
    stub = coordinator_place
    with pytest.raises(grpc.RpcError) as excinfo:
        stub.RefreshReservation(labgrid_coordinator_pb2.RefreshReservationRequest(reservation_id="nonexistent"))

    assert excinfo.value.code() == grpc.StatusCode.FAILED_PRECONDITION
    assert excinfo.value.details() == "Reservation nonexistent does not exist"


def wait_for_list_place_resources(stub, name, expected_count, timeout=5.0):
    deadline = monotonic() + timeout
    request = labgrid_coordinator_pb2.ListPlaceResourcesRequest(name=name)
    while monotonic() < deadline:
        res = stub.ListPlaceResources(request)
        if len(res.resources) == expected_count:
            return res
        sleep(0.1)
    return stub.ListPlaceResources(request)


def wait_for_list_resources(stub, expected_count, filter_expr=None, timeout=5.0):
    deadline = monotonic() + timeout
    kwargs = {}
    if filter_expr is not None:
        kwargs["filter"] = filter_expr
    request = labgrid_coordinator_pb2.ListResourcesRequest(**kwargs)
    while monotonic() < deadline:
        res = stub.ListResources(request)
        if len(res.resources) == expected_count:
            return res
        sleep(0.1)
    return stub.ListResources(request)


def test_coordinator_list_place_resources(coordinator, coordinator_place, exporter):
    stub = coordinator_place
    res = stub.AddPlaceMatch(
        labgrid_coordinator_pb2.AddPlaceMatchRequest(placename="test", pattern=LIST_PLACE_RESOURCES_PATTERN)
    )
    assert res
    res = wait_for_list_place_resources(stub, "test", 1)
    assert len(res.resources) == 1
    assert res.resources[0].cls == "NetworkSerialPort"
    assert res.resources[0].path.exporter_name == "testhost"
    assert res.resources[0].path.group_name == "ClsNotEqualResourceName"
    assert res.resources[0].path.resource_name == "ExampleResource"


def test_coordinator_list_place_resources_no_matches(coordinator, coordinator_place, exporter):
    stub = coordinator_place
    res = stub.AddPlaceMatch(
        labgrid_coordinator_pb2.AddPlaceMatchRequest(placename="test", pattern=LIST_PLACE_RESOURCES_PATTERN)
    )
    assert res
    res = wait_for_list_place_resources(stub, "test", 1)
    assert len(res.resources) == 1
    res = stub.DeletePlaceMatch(
        labgrid_coordinator_pb2.DeletePlaceMatchRequest(placename="test", pattern=LIST_PLACE_RESOURCES_PATTERN)
    )
    assert res
    res = stub.ListPlaceResources(labgrid_coordinator_pb2.ListPlaceResourcesRequest(name="test"))
    assert res
    assert len(res.resources) == 0


def test_coordinator_list_place_resources_place_does_not_exist(coordinator, coordinator_place):
    stub = coordinator_place
    with pytest.raises(grpc.RpcError) as excinfo:
        stub.ListPlaceResources(labgrid_coordinator_pb2.ListPlaceResourcesRequest(name="test_nonexistant_place"))

    assert excinfo.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert excinfo.value.details() == "Place test_nonexistant_place does not exist"


def test_coordinator_list_place_resources_name_not_provided(coordinator, coordinator_place):
    stub = coordinator_place
    with pytest.raises(grpc.RpcError) as excinfo:
        stub.ListPlaceResources(labgrid_coordinator_pb2.ListPlaceResourcesRequest())

    assert excinfo.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert excinfo.value.details() == "name was not a string"


def test_coordinator_list_resources(coordinator, coordinator_place, exporter):
    stub = coordinator_place
    res = wait_for_list_resources(stub, 5)
    assert len(res.resources) == 5


def test_coordinator_list_resources_filter_on_resource_name(coordinator, coordinator_place, exporter):
    stub = coordinator_place
    res = wait_for_list_resources(stub, 1, filter_expr="path.resource_name == 'ExampleResource'")
    assert len(res.resources) == 1
    assert res.resources[0].cls == "NetworkSerialPort"
    assert res.resources[0].path.exporter_name == "testhost"
    assert res.resources[0].path.group_name == "ClsNotEqualResourceName"
    assert res.resources[0].path.resource_name == "ExampleResource"


def test_coordinator_list_resources_pagination_not_supported(coordinator, channel_stub):
    with pytest.raises(grpc.RpcError) as excinfo:
        channel_stub.ListResources(labgrid_coordinator_pb2.ListResourcesRequest(page_size=1))

    assert excinfo.value.code() == grpc.StatusCode.UNIMPLEMENTED
    assert excinfo.value.details() == "ListResources does not yet support pagination"


def test_coordinator_list_resources_invalid_filter(coordinator, channel_stub):
    with pytest.raises(grpc.RpcError) as excinfo:
        channel_stub.ListResources(labgrid_coordinator_pb2.ListResourcesRequest(filter="("))

    assert excinfo.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert excinfo.value.details().startswith("Invalid filter:")


def test_coordinator_list_resources_filter_must_be_boolean(coordinator, channel_stub, exporter):
    res = wait_for_list_resources(channel_stub, 5)
    assert len(res.resources) == 5

    with pytest.raises(grpc.RpcError) as excinfo:
        channel_stub.ListResources(labgrid_coordinator_pb2.ListResourcesRequest(filter="path.resource_name"))

    assert excinfo.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert excinfo.value.details() == "Filter must evaluate to a boolean"


def test_coordinator_list_places(coordinator, coordinator_place):
    stub = coordinator_place
    res = stub.ListPlaces(labgrid_coordinator_pb2.ListPlacesRequest())
    assert res
    assert len(res.places) == 1
    assert res.places[0].name == "test"


def test_coordinator_list_places_pagination_not_supported(coordinator, channel_stub):
    with pytest.raises(grpc.RpcError) as excinfo:
        channel_stub.ListPlaces(labgrid_coordinator_pb2.ListPlacesRequest(page_size=1))

    assert excinfo.value.code() == grpc.StatusCode.UNIMPLEMENTED
    assert excinfo.value.details() == "ListPlaces does not yet support pagination"


def test_coordinator_list_places_filter_on_place_name(coordinator, coordinator_place):
    stub = coordinator_place
    res = stub.ListPlaces(labgrid_coordinator_pb2.ListPlacesRequest(filter="name == 'test'"))
    assert res
    assert len(res.places) == 1
    assert res.places[0].name == "test"


def test_coordinator_list_places_filter_on_place_name_no_matches(coordinator, coordinator_place):
    stub = coordinator_place
    res = stub.ListPlaces(labgrid_coordinator_pb2.ListPlacesRequest(filter="name == 'missing'"))
    assert res
    assert len(res.places) == 0


def test_coordinator_list_places_filter_invalid_syntax(coordinator, coordinator_place):
    stub = coordinator_place
    with pytest.raises(grpc.RpcError) as excinfo:
        stub.ListPlaces(labgrid_coordinator_pb2.ListPlacesRequest(filter="name =="))
    assert excinfo.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert "Invalid filter" in excinfo.value.details()


def test_coordinator_list_places_filter_unknown_field(coordinator, coordinator_place):
    stub = coordinator_place
    with pytest.raises(grpc.RpcError) as excinfo:
        stub.ListPlaces(labgrid_coordinator_pb2.ListPlacesRequest(filter="missing == 'x'"))
    assert excinfo.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert "Invalid filter" in excinfo.value.details()


def test_coordinator_list_places_filter_must_evaluate_to_boolean(coordinator, coordinator_place):
    stub = coordinator_place
    with pytest.raises(grpc.RpcError) as excinfo:
        stub.ListPlaces(labgrid_coordinator_pb2.ListPlacesRequest(filter="name"))
    assert excinfo.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert "Filter must evaluate to a boolean" in excinfo.value.details()


def test_coordinator_list_reservations(coordinator, coordinator_place, coordinator_reservation):
    stub = coordinator_place
    res = stub.ListReservations(labgrid_coordinator_pb2.ListReservationsRequest())
    assert res
    assert len(res.reservations) == 1
    assert res.reservations[0].token == coordinator_reservation


def test_coordinator_list_reservations_pagination_not_supported(coordinator, channel_stub):
    with pytest.raises(grpc.RpcError) as excinfo:
        channel_stub.ListReservations(labgrid_coordinator_pb2.ListReservationsRequest(page_size=1))

    assert excinfo.value.code() == grpc.StatusCode.UNIMPLEMENTED
    assert excinfo.value.details() == "ListReservations does not yet support pagination"


def test_coordinator_list_reservations_filter_on_token(coordinator, coordinator_place, coordinator_reservation):
    stub = coordinator_place
    res = stub.ListReservations(
        labgrid_coordinator_pb2.ListReservationsRequest(filter=f"token == '{coordinator_reservation}'")
    )
    assert res
    assert len(res.reservations) == 1
    assert res.reservations[0].token == coordinator_reservation


def test_coordinator_list_reservations_filter_on_token_no_matches(
    coordinator, coordinator_place, coordinator_reservation
):
    stub = coordinator_place
    res = stub.ListReservations(labgrid_coordinator_pb2.ListReservationsRequest(filter="token == '1234'"))
    assert res
    assert len(res.reservations) == 0


def test_coordinator_list_reservations_filter_invalid_syntax(coordinator, coordinator_place, coordinator_reservation):
    stub = coordinator_place
    with pytest.raises(grpc.RpcError) as excinfo:
        stub.ListReservations(labgrid_coordinator_pb2.ListReservationsRequest(filter="tokens =="))
    assert excinfo.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert "Invalid filter" in excinfo.value.details()


def test_coordinator_list_reservations_filter_unknown_field(coordinator, coordinator_place, coordinator_reservation):
    stub = coordinator_place
    with pytest.raises(grpc.RpcError) as excinfo:
        stub.ListReservations(labgrid_coordinator_pb2.ListReservationsRequest(filter="missing == 'x'"))
    assert excinfo.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert "Invalid filter" in excinfo.value.details()


def test_coordinator_list_reservations_filter_must_evaluate_to_boolean(
    coordinator, coordinator_place, coordinator_reservation
):
    stub = coordinator_place
    with pytest.raises(grpc.RpcError) as excinfo:
        stub.ListReservations(labgrid_coordinator_pb2.ListReservationsRequest(filter="token"))
    assert excinfo.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert "Filter must evaluate to a boolean" in excinfo.value.details()


def test_coordinator_propagate_identity_on_lease(coordinator, channel_stub, tmpdir):
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
            "python -m labgrid.remote.client reserve name=place1 --wait",
            cwd=tmpdir,
            env=os.environ | {"LG_HOSTNAME": "somehost", "LG_USERNAME": "someuser"},
        ) as spawn_acquire:
            spawn_acquire.expect(r"Reservation '([^']+)':")
            reservation_id = spawn_acquire.match.group(1).decode()
            spawn_acquire.expect(pexpect.EOF)

        with pexpect.spawn(
            f"python -m labgrid.remote.client -p +{reservation_id} lease",
            cwd=tmpdir,
            env=os.environ | {"LG_HOSTNAME": "somehost", "LG_USERNAME": "someuser"},
        ) as spawn_acquire:
            spawn_acquire.expect("leased place place1")
            spawn_acquire.expect(pexpect.EOF)

        spawn.expect("INFO:root:Example/NetworkService leased by somehost/someuser")

        spawn.kill(signal.SIGTERM)
        spawn.expect(pexpect.EOF)

class ReservationAcquireAbortError(Exception):
    pass


class ReservationAcquireContext:
    def peer(self):
        return "test-peer"

    def invocation_metadata(self):
        return ()

    async def abort(self, code, details):
        raise ReservationAcquireAbortError(details)


def make_coordinator_with_reserved_place():
    coordinator = Coordinator.__new__(Coordinator)
    coordinator.lock = asyncio.Lock()
    coordinator.clients = {"test-peer": SimpleNamespace(name="testuser", queue=asyncio.Queue())}
    coordinator.exporters = {}
    coordinator.places = {}
    coordinator.reservations = {}
    coordinator.save_scheduled = False
    coordinator.reservation_retry_cooldown = 60.0
    coordinator.reservation_place_cooldowns = {}

    reservation = Reservation(
        owner="testuser",
        id="reservation-id",
        state=ReservationState.allocated,
        filters={"main": {"board": "test"}},
        allocations={"main": ["test"]},
        timeout=time.time() + 60,
    )
    place = Place("test", tags={"board": "test"}, reservation=reservation.id)
    coordinator.reservations[reservation.id] = reservation
    coordinator.places[place.name] = place
    return coordinator, reservation, place


def test_acquire_failure_returns_reservation_to_waiting_and_cools_place():
    async def fail_acquire(_place, _resources):
        raise CoordinatorError("acquire failed")

    async def run_test():
        coordinator, reservation, place = make_coordinator_with_reserved_place()
        coordinator._acquire_resources = fail_acquire

        with pytest.raises(ReservationAcquireAbortError, match="Failed to acquire resources"):
            await coordinator.AcquirePlace(
                labgrid_coordinator_pb2.AcquirePlaceRequest(placename=place.name),
                ReservationAcquireContext(),
            )

        assert reservation.state is ReservationState.waiting
        assert reservation.allocations == {}
        assert place.reservation is None
        assert place.acquired is None
        assert place.name in coordinator.reservation_place_cooldowns

        async with coordinator.lock:
            await coordinator.schedule_reservations()

        assert reservation.state is ReservationState.waiting
        assert reservation.allocations == {}
        assert place.reservation is None

    asyncio.run(run_test())

def test_lease_failure_returns_reservation_to_waiting_and_cools_place():
    async def fail_lease(_place, _owner, _duration):
        raise CoordinatorError("lease failed")

    async def run_test():
        coordinator, reservation, place = make_coordinator_with_reserved_place()
        coordinator.default_lease_duration = 5
        coordinator._lease_place_resources = fail_lease

        with pytest.raises(ReservationAcquireAbortError, match="Failed to lease resources"):
            await coordinator.LeasePlace(
                labgrid_coordinator_pb2.LeasePlaceRequest(placename=place.name),
                ReservationAcquireContext(),
            )

        assert reservation.state is ReservationState.waiting
        assert reservation.allocations == {}
        assert reservation.lease_start_time == 0.0
        assert place.reservation is None
        assert place.acquired is None
        assert place.name in coordinator.reservation_place_cooldowns

        async with coordinator.lock:
            await coordinator.schedule_reservations()

        assert reservation.state is ReservationState.waiting
        assert reservation.allocations == {}
        assert place.reservation is None

    asyncio.run(run_test())
