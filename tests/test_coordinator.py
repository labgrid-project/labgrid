import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

import grpc
import pytest

import labgrid.remote.generated.labgrid_coordinator_pb2 as labgrid_coordinator_pb2
import labgrid.remote.generated.labgrid_coordinator_pb2_grpc as labgrid_coordinator_pb2_grpc
from labgrid.remote.coordinator import Coordinator, ExporterError, ExporterSession, warn_if_slow


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


def test_warn_if_slow_logs_over_limit(caplog):
    with caplog.at_level(logging.WARNING):
        with warn_if_slow("op", limit=0.0):
            pass
    assert "op: real" in caplog.text


async def _aiter(messages):
    for msg in messages:
        yield msg


def test_exporterstream_duplicate_name_aborts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    async def run():
        coordinator = Coordinator()
        try:
            coordinator.exporters["existing-peer"] = ExporterSession(
                coordinator, "existing-peer", "dup", asyncio.Queue(), "1.0.0"
            )

            msg = labgrid_coordinator_pb2.ExporterInMessage()
            msg.startup.version = "2.0.0"
            msg.startup.name = "dup"

            context = MagicMock()
            context.peer.return_value = "new-peer"
            context.abort = AsyncMock()

            stream = coordinator.ExporterStream(_aiter([msg]), context)
            with pytest.raises(ExporterError, match="already connected"):
                async for _ in stream:
                    pass

            context.abort.assert_awaited_once()
        finally:
            for task in coordinator.poll_tasks:
                task.cancel()

    asyncio.run(run())


def test_exporterstream_times_out_during_startup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    async def fake_wait(fs, **kwargs):
        return set(), set(fs)

    monkeypatch.setattr(asyncio, "wait", fake_wait)

    async def hanging_aiter():
        await asyncio.Future()
        yield  # pragma: no cover

    async def run():
        coordinator = Coordinator()
        try:
            context = MagicMock()
            context.peer.return_value = "new-peer"

            stream = coordinator.ExporterStream(hanging_aiter(), context)
            with pytest.raises(ExporterError, match="timed out during startup"):
                async for _ in stream:
                    pass
        finally:
            for task in coordinator.poll_tasks:
                task.cancel()

    asyncio.run(run())
