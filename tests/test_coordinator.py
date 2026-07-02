from time import monotonic, sleep

import grpc
import pytest
import labgrid.remote.generated.labgrid_coordinator_pb2_grpc as labgrid_coordinator_pb2_grpc
import labgrid.remote.generated.labgrid_coordinator_pb2 as labgrid_coordinator_pb2

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


def test_startup(coordinator):
    pass


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
    with pytest.raises(Exception, match=r".Place test is not acquired.*"):
        stub.UnsharePlace(labgrid_coordinator_pb2.UnsharePlaceRequest(name="test", user="othertest"))


def test_coordinator_place_unshare_not_shared(coordinator, coordinator_place):
    stub = coordinator_place
    res = stub.AcquirePlace(labgrid_coordinator_pb2.AcquirePlaceRequest(placename="test"))
    assert res
    with pytest.raises(Exception, match=r".Place test is not shared with othertest.*"):
        stub.UnsharePlace(labgrid_coordinator_pb2.UnsharePlaceRequest(name="test", user="othertest"))


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
