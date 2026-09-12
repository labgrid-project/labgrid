import os
import signal

import grpc
import pexpect
import pytest
import labgrid.remote.generated.labgrid_coordinator_pb2_grpc as labgrid_coordinator_pb2_grpc
import labgrid.remote.generated.labgrid_coordinator_pb2 as labgrid_coordinator_pb2


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


def test_coordinator_propagate_identity_on_lock(coordinator, channel_stub, tmpdir):
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

        spawn.kill(signal.SIGTERM)
        spawn.expect(pexpect.EOF)


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
            spawn_acquire.expect(r"Reservation '([^']+)':", timeout=1)
            reservation_id = spawn_acquire.match.group(1).decode()
            spawn_acquire.expect(pexpect.EOF)

        with pexpect.spawn(
            f"python -m labgrid.remote.client -p +{reservation_id} lease",
            cwd=tmpdir,
            env=os.environ | {"LG_HOSTNAME": "somehost", "LG_USERNAME": "someuser"},
        ) as spawn_acquire:
            spawn_acquire.expect("leased place place1", timeout=1)
            spawn_acquire.expect(pexpect.EOF)

        spawn.expect("INFO:root:Example/NetworkService leased by somehost/someuser", timeout=1)

        spawn.kill(signal.SIGTERM)
        spawn.expect(pexpect.EOF)
