import grpc
import grpc._channel
import pytest

import labgrid.remote.generated.labgrid_coordinator_pb2 as labgrid_coordinator_pb2
import labgrid.remote.generated.labgrid_coordinator_pb2_grpc as labgrid_coordinator_pb2_grpc


class ChannelStub:
    """Context that instantiates a ClientSession with an optional session name"""

    def __init__(self, session_name=""):
        self._session_name = session_name
        self._stream = None
        self._channel = grpc.insecure_channel("127.0.0.1:20408", options=(("grpc.use_local_subchannel_pool", 1),))
        self._stub = labgrid_coordinator_pb2_grpc.CoordinatorStub(self._channel)

    def __enter__(self):
        self.start()
        return self.stub

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    @property
    def stub(self):
        return self._stub

    def start(self):
        import queue

        queue = queue.Queue()

        def generate_startup(queue):
            msg = labgrid_coordinator_pb2.ClientInMessage()
            msg.startup.version = "2.0.0"
            msg.startup.name = "testclient"
            msg.startup.session = self._session_name
            messages = [msg]
            for msg in messages:
                yield msg
            while True:
                msg = queue.get()
                yield msg
                queue.task_done()

        self._stream = self._stub.ClientStream(generate_startup(queue))

    def stop(self):
        self._channel.close()


def _add_place(stub, name):
    place = labgrid_coordinator_pb2.AddPlaceRequest(name=name)
    res = stub.AddPlace(place)
    assert res, f"There was an error: {res}"


def test_acquire_place(coordinator):
    """A place can be acquired in a session"""
    with ChannelStub("session_1") as stub:
        _add_place(stub, "test")
        res = stub.AcquirePlace(labgrid_coordinator_pb2.AcquirePlaceRequest(placename="test", session="session_1"))
        assert res


def test_reservation(coordinator):
    """A reservation can be created in a session"""
    with ChannelStub("session_1") as stub:
        _add_place(stub, "test")
        tags = {"board": "test"}
        res = stub.SetPlaceTags(labgrid_coordinator_pb2.SetPlaceTagsRequest(placename="test", tags=tags))
        res = stub.CreateReservation(
            labgrid_coordinator_pb2.CreateReservationRequest(
                filters={
                    "main": labgrid_coordinator_pb2.Reservation.Filter(filter=tags),
                },
                prio=1.0,
                session="session_1",
            )
        )
        assert res


def test_reserve_and_acquire(coordinator):
    """A reservation can be created and place acquired in a session"""
    with ChannelStub("session_1") as stub:
        _add_place(stub, "test")
        tags = {"board": "test"}
        res = stub.SetPlaceTags(labgrid_coordinator_pb2.SetPlaceTagsRequest(placename="test", tags=tags))
        res = stub.CreateReservation(
            labgrid_coordinator_pb2.CreateReservationRequest(
                filters={
                    "main": labgrid_coordinator_pb2.Reservation.Filter(filter=tags),
                },
                prio=1.0,
                session="session_1",
            )
        )
        assert res
        res = stub.AcquirePlace(labgrid_coordinator_pb2.AcquirePlaceRequest(placename="test", session="session_1"))
        assert res


def test_acquire_place_release_session(coordinator):
    """A place is unlocked if its session is closed"""
    with ChannelStub("session_1") as stub:
        _add_place(stub, "test")
        res = stub.AcquirePlace(labgrid_coordinator_pb2.AcquirePlaceRequest(placename="test", session="session_1"))
        assert res

    with ChannelStub() as stub:
        with pytest.raises(grpc._channel._InactiveRpcError):
            res = stub.AllowPlace(labgrid_coordinator_pb2.AllowPlaceRequest(placename="test"))


def test_reservation_release_session(coordinator):
    """A reservation is cancelled if its session is closed"""
    with ChannelStub("session_1") as stub:
        tags = {"board": "test"}
        _add_place(stub, "test")
        res = stub.CreateReservation(
            labgrid_coordinator_pb2.CreateReservationRequest(
                filters={
                    "main": labgrid_coordinator_pb2.Reservation.Filter(filter=tags),
                },
                prio=1.0,
                session="session_1",
            )
        )
        assert res
        token = res.reservation.token

    with ChannelStub() as stub:
        with pytest.raises(grpc._channel._InactiveRpcError):
            stub.PollReservation(labgrid_coordinator_pb2.PollReservationRequest(token=token))


def test_reservation_acquire_place_release_session(coordinator):
    """A place is unlocked and its reservation is cancelled if its session is closed"""
    with ChannelStub("session_1") as stub:
        _add_place(stub, "test")
        tags = {"board": "test"}
        res = stub.SetPlaceTags(labgrid_coordinator_pb2.SetPlaceTagsRequest(placename="test", tags=tags))
        assert res
        res = stub.CreateReservation(
            labgrid_coordinator_pb2.CreateReservationRequest(
                filters={
                    "main": labgrid_coordinator_pb2.Reservation.Filter(filter=tags),
                },
                prio=1.0,
                session="session_1",
            )
        )
        assert res
        token = res.reservation.token
        res = stub.AcquirePlace(labgrid_coordinator_pb2.AcquirePlaceRequest(placename="test", session="session_1"))
        assert res

    with ChannelStub() as stub:
        with pytest.raises(grpc._channel._InactiveRpcError):
            stub.PollReservation(labgrid_coordinator_pb2.PollReservationRequest(token=token))
        with pytest.raises(grpc._channel._InactiveRpcError):
            res = stub.AllowPlace(labgrid_coordinator_pb2.AllowPlaceRequest(placename="test"))


def test_acquire_place_no_session(coordinator):
    """A place cannot be acquired if the session doesn't exist"""
    with ChannelStub() as stub:
        _add_place(stub, "test")
        with pytest.raises(grpc._channel._InactiveRpcError):
            stub.AcquirePlace(labgrid_coordinator_pb2.AcquirePlaceRequest(placename="test", session="session_1"))


def test_reservation_no_session(coordinator):
    """A reservation cannot be created if the session doesn't exist"""
    with ChannelStub() as stub:
        _add_place(stub, "test")
        tags = {"board": "test"}
        res = stub.SetPlaceTags(labgrid_coordinator_pb2.SetPlaceTagsRequest(placename="test", tags=tags))
        assert res
        with pytest.raises(grpc._channel._InactiveRpcError):
            res = stub.CreateReservation(
                labgrid_coordinator_pb2.CreateReservationRequest(
                    filters={
                        "main": labgrid_coordinator_pb2.Reservation.Filter(filter=tags),
                    },
                    prio=1.0,
                    session="session_1",
                )
            )


def test_multiple_reservations_places(coordinator):
    """Multiple reservations and places can be held in one session"""
    with ChannelStub("session_1") as stub:
        _add_place(stub, "test_1")
        _add_place(stub, "test_2")
        tags = {"board": "test"}
        res = stub.SetPlaceTags(labgrid_coordinator_pb2.SetPlaceTagsRequest(placename="test_1", tags=tags))
        assert res
        res = stub.SetPlaceTags(labgrid_coordinator_pb2.SetPlaceTagsRequest(placename="test_2", tags=tags))
        assert res
        res = stub.CreateReservation(
            labgrid_coordinator_pb2.CreateReservationRequest(
                filters={
                    "main": labgrid_coordinator_pb2.Reservation.Filter(filter=tags),
                },
                prio=1.0,
                session="session_1",
            )
        )
        assert res
        token_1 = res.reservation.token
        res = stub.CreateReservation(
            labgrid_coordinator_pb2.CreateReservationRequest(
                filters={
                    "main": labgrid_coordinator_pb2.Reservation.Filter(filter=tags),
                },
                prio=1.0,
                session="session_1",
            )
        )
        assert res
        token_2 = res.reservation.token
        res = stub.AcquirePlace(labgrid_coordinator_pb2.AcquirePlaceRequest(placename="test_1", session="session_1"))
        assert res
        res = stub.AcquirePlace(labgrid_coordinator_pb2.AcquirePlaceRequest(placename="test_2", session="session_1"))
        assert res

    with ChannelStub("") as stub:
        with pytest.raises(grpc._channel._InactiveRpcError):
            stub.PollReservation(labgrid_coordinator_pb2.PollReservationRequest(token=token_1))
        with pytest.raises(grpc._channel._InactiveRpcError):
            stub.AllowPlace(labgrid_coordinator_pb2.AllowPlaceRequest(placename="test_1"))
        with pytest.raises(grpc._channel._InactiveRpcError):
            stub.PollReservation(labgrid_coordinator_pb2.PollReservationRequest(token=token_2))
        with pytest.raises(grpc._channel._InactiveRpcError):
            stub.AllowPlace(labgrid_coordinator_pb2.AllowPlaceRequest(placename="test_2"))


def test_multiple_sessions(coordinator):
    """Multiple sessions can coexist without interference"""
    # Setup session 1, create reservation and acquire place
    with ChannelStub("session_1") as stub_1:
        _add_place(stub_1, "test_1")
        tags = {"board_1": "test_1"}
        res = stub_1.SetPlaceTags(labgrid_coordinator_pb2.SetPlaceTagsRequest(placename="test_1", tags=tags))
        assert res
        res = stub_1.CreateReservation(
            labgrid_coordinator_pb2.CreateReservationRequest(
                filters={
                    "main": labgrid_coordinator_pb2.Reservation.Filter(filter=tags),
                },
                prio=1.0,
                session="session_1",
            )
        )
        assert res
        token_1 = res.reservation.token
        res = stub_1.AcquirePlace(labgrid_coordinator_pb2.AcquirePlaceRequest(placename="test_1", session="session_1"))
        assert res

        # Setup session 2, create reservation and acquire place
        with ChannelStub("session_2") as stub_2:
            _add_place(stub_2, "test_2")
            tags = {"board_2": "test_2"}
            res = stub_2.SetPlaceTags(labgrid_coordinator_pb2.SetPlaceTagsRequest(placename="test_2", tags=tags))
            assert res
            res = stub_2.CreateReservation(
                labgrid_coordinator_pb2.CreateReservationRequest(
                    filters={
                        "main": labgrid_coordinator_pb2.Reservation.Filter(filter=tags),
                    },
                    prio=1.0,
                    session="session_2",
                )
            )
            assert res
            token_2 = res.reservation.token
            res = stub_2.AcquirePlace(
                labgrid_coordinator_pb2.AcquirePlaceRequest(placename="test_2", session="session_2")
            )
            assert res

        # Assert the reservation and place under session 2 have been released
        with pytest.raises(grpc._channel._InactiveRpcError):
            stub_1.PollReservation(labgrid_coordinator_pb2.PollReservationRequest(token=token_2))
        with pytest.raises(grpc._channel._InactiveRpcError):
            stub_1.AllowPlace(labgrid_coordinator_pb2.AllowPlaceRequest(placename="test_2"))

        # Assert the reservation and place under session 1 are held
        res = stub_1.PollReservation(labgrid_coordinator_pb2.PollReservationRequest(token=token_1))
        assert res
        res = stub_1.AllowPlace(labgrid_coordinator_pb2.AllowPlaceRequest(placename="test_1"))
        assert res
