import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import grpc
import pytest

from labgrid.remote.common import Place
from labgrid.remote.coordinator import Coordinator, CoordinatorError, ResourceImport
from labgrid.remote.generated import labgrid_coordinator_pb2 as pb2


class RpcAborted(Exception):
    def __init__(self, code, details):
        super().__init__(details)
        self.code = code


class Context:
    def __init__(self, metadata=()):
        self.metadata = metadata

    def peer(self):
        return "test-peer"

    def invocation_metadata(self):
        return self.metadata

    async def abort(self, code, details):
        raise RpcAborted(code, details)


@pytest.fixture
def event_coordinator():
    coordinator = Coordinator.__new__(Coordinator)
    coordinator.lock = asyncio.Lock()
    coordinator.clients = {"test-peer": SimpleNamespace(name="host/alice")}
    coordinator.exporters = {}
    coordinator.reservations = {}
    coordinator._publish_place = Mock()
    coordinator.save_later = Mock()
    coordinator._release_resources = AsyncMock(wraps=coordinator._release_resources)
    place = Place("test-place")
    coordinator.places = {place.name: place}
    return coordinator, place


def acquired_resource(place):
    resource = ResourceImport(
        data={"cls": "NetworkService", "params": {}, "acquired": place.name, "avail": True},
        path=("test-exporter", "group", "NetworkService", "service"),
    )
    # Releasing an orphaned resource exercises local cleanup without an exporter.
    resource.orphaned = True
    return resource


def coordinator_events(caplog):
    return [record for record in caplog.records if record.name == "coordinator.events"]


@pytest.mark.parametrize("owner", [None, "host/current-owner"], ids=["already-free", "different-owner"])
def test_release_skip_preserves_place_and_reports_skip(event_coordinator, caplog, owner):
    coordinator, place = event_coordinator
    place.acquired = owner
    if owner is not None:
        place.allowed = {"host/shared-user"}
        place.acquired_resources = [acquired_resource(place)]
    before = place.asdict()

    with caplog.at_level(logging.INFO, logger="coordinator.events"):
        response = asyncio.run(coordinator.ReleasePlace(
            pb2.ReleasePlaceRequest(placename=place.name, fromuser="host/previous-owner"), Context()
        ))

    assert isinstance(response, pb2.ReleasePlaceResponse)
    assert place.asdict() == before
    coordinator._release_resources.assert_not_awaited()
    coordinator._publish_place.assert_not_called()
    coordinator.save_later.assert_not_called()
    events = coordinator_events(caplog)
    assert len(events) == 1
    assert events[0].__dict__["event.name"] == "place.released_skipped"
    assert events[0].__dict__["place.name"] == place.name
    assert "skipped" in events[0].getMessage()


@pytest.mark.parametrize("metadata_identity", [False, True], ids=["stream", "metadata"])
def test_release_event_follows_resource_cleanup_and_publication(
    event_coordinator, caplog, monkeypatch, metadata_identity
):
    coordinator, place = event_coordinator
    context = Context()
    if metadata_identity:
        coordinator.clients.clear()
        context = Context((("x-lg-hostname", "host"), ("x-lg-name", "alice")))
    place.acquired = "host/alice"
    place.allowed = {"host/shared-user"}
    place.acquired_resources = [acquired_resource(place)]
    states_at_event = []

    class StateObserver(logging.Handler):
        def emit(self, record):
            states_at_event.append((
                place.acquired,
                set(place.allowed),
                list(place.acquired_resources),
                coordinator._publish_place.call_count,
                coordinator.save_later.call_count,
            ))

    monkeypatch.setattr(logging.getLogger("coordinator.events"), "handlers", [StateObserver()])
    with caplog.at_level(logging.INFO, logger="coordinator.events"):
        response = asyncio.run(coordinator.ReleasePlace(
            pb2.ReleasePlaceRequest(placename=place.name, fromuser="host/alice"), context
        ))

    assert isinstance(response, pb2.ReleasePlaceResponse)
    coordinator._release_resources.assert_awaited_once()
    coordinator._publish_place.assert_called_once_with(place)
    assert states_at_event == [(None, set(), [], 1, 1)]
    events = coordinator_events(caplog)
    assert len(events) == 1
    assert events[0].__dict__["event.name"] == "place.released"
    assert events[0].__dict__["event.outcome"] == "success"
    assert events[0].__dict__["user.id"] == "host/alice"
    assert events[0].getMessage() == "test-place: place released"


@pytest.mark.parametrize("metadata_identity", [False, True], ids=["stream", "metadata"])
def test_failed_acquire_reports_acquire_failure_after_rollback(event_coordinator, caplog, metadata_identity):
    coordinator, place = event_coordinator
    context = Context()
    if metadata_identity:
        coordinator.clients.clear()
        context = Context((("x-lg-hostname", "host"), ("x-lg-name", "alice")))
    coordinator._acquire_resources = AsyncMock(side_effect=CoordinatorError("exporter rejected acquisition"))
    before = place.asdict()

    with caplog.at_level(logging.INFO, logger="coordinator.events"):
        with pytest.raises(RpcAborted, match="Failed to acquire resources") as error:
            asyncio.run(coordinator.AcquirePlace(pb2.AcquirePlaceRequest(placename=place.name), context))

    assert error.value.code is grpc.StatusCode.FAILED_PRECONDITION
    assert place.asdict() == before
    coordinator._acquire_resources.assert_awaited_once()
    coordinator._publish_place.assert_not_called()
    coordinator.save_later.assert_not_called()
    events = coordinator_events(caplog)
    assert len(events) == 1
    assert events[0].__dict__["event.name"] == "place.acquired"
    assert events[0].__dict__["event.outcome"] == "failure"
    assert events[0].__dict__["place.name"] == place.name
    assert events[0].__dict__["user.id"] == "host/alice"
    assert events[0].getMessage() == "test-place: place.acquired failed for host/alice"
    assert events[0].exc_info[1] is error.value


def test_failed_release_preserves_ownership_and_publishes_place_before_failure_event(event_coordinator, caplog):
    coordinator, place = event_coordinator
    place.acquired = "host/alice"
    place.allowed = {"host/shared-user"}
    coordinator._release_resources = AsyncMock(side_effect=CoordinatorError("exporter rejected release"))

    with caplog.at_level(logging.INFO, logger="coordinator.events"):
        with pytest.raises(RpcAborted, match="Failed to release resources.*exporter rejected release") as error:
            asyncio.run(coordinator.ReleasePlace(pb2.ReleasePlaceRequest(placename=place.name), Context()))

    assert error.value.code is grpc.StatusCode.FAILED_PRECONDITION
    assert place.acquired == "host/alice"
    assert place.allowed == {"host/shared-user"}
    coordinator._publish_place.assert_called_once_with(place)
    coordinator.save_later.assert_called_once_with()
    events = coordinator_events(caplog)
    assert len(events) == 1
    assert events[0].__dict__["event.name"] == "place.released"
    assert events[0].__dict__["event.outcome"] == "failure"
    assert events[0].exc_info[1] is error.value
