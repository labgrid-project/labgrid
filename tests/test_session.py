"""Offline session and CLI compatibility tests with a mocked coordinator."""

import asyncio
import inspect
import traceback
from unittest.mock import AsyncMock, MagicMock

import grpc
import pytest

from labgrid import Environment
from labgrid.remote import client
from labgrid.remote import session as session_module
from labgrid.remote.common import Place, Reservation, ReservationState, ResourceEntry, ResourceMatch
from labgrid.remote.generated import labgrid_coordinator_pb2 as pb2
from labgrid.remote.session import ClientSession, ReservationFilter, ServerError, Tag, UserError
from labgrid.resource.common import ResourceManager
from labgrid.resource.remote import RemotePlace


@pytest.fixture
def session(monkeypatch):
    loop = asyncio.new_event_loop()
    channel = MagicMock(close=AsyncMock())
    stub = MagicMock()
    for name in (
        "AddPlace",
        "DeletePlace",
        "AddPlaceAlias",
        "DeletePlaceAlias",
        "SetPlaceComment",
        "SetPlaceTags",
        "AddPlaceMatch",
        "DeletePlaceMatch",
        "AcquirePlace",
        "ReleasePlace",
        "AllowPlace",
        "CreateReservation",
        "CancelReservation",
        "PollReservation",
        "GetReservations",
    ):
        setattr(stub, name, AsyncMock())
    monkeypatch.setattr(session_module.grpc.aio, "insecure_channel", lambda **kwargs: channel)
    monkeypatch.setattr(session_module.labgrid_coordinator_pb2_grpc, "CoordinatorStub", lambda channel: stub)
    result = ClientSession("unused:20408", loop, username="tester", hostname="testhost")
    result.sync_with_coordinator = AsyncMock(return_value=True)
    result.places["bench"] = Place("bench", created=1.0, changed=2.0)
    yield result
    loop.run_until_complete(result.close())
    loop.close()


def run(session, awaitable):
    return session.loop.run_until_complete(awaitable)


def commands(session, *arguments):
    args = client.get_parser().parse_args(["-p", "bench", *arguments])
    return client.ClientCommands(session, args, "labgrid-client")


def reservation_message():
    return pb2.Reservation(owner="testhost/tester", token="test-token", state=ReservationState.allocated.value)


def test_public_session_contract():
    fields = inspect.signature(ClientSession).parameters
    assert not {"args", "prog", "monitor"} & fields.keys()
    assert not hasattr(ClientSession, "print_places")
    assert client.ClientSession is ClientSession
    assert client.ClientCommands.console.needs_target
    assert client.ClientCommands.export.needs_target


def test_missing_place_name_has_separate_cli_guidance(session):
    with pytest.raises(session_module.MissingPlaceNameError) as error:
        run(session, session.add_place(""))
    assert error.value.args == ("missing place name",)
    cli = commands(session, "create")
    cli.args.place = None
    with pytest.raises(UserError) as error:
        run(session, cli.add_place())
    assert error.value.args == ("missing place name. Set with -p <place> or via env var LG_PLACE",)
    assert "".join(traceback.format_exception(error.value)).count("Traceback (most recent call last):") == 1
    session.stub.AddPlace.assert_not_awaited()


@pytest.mark.parametrize(
    "owner, operation, description, hint",
    [
        (
            "other/user",
            "get_acquired_place",
            "place bench is not acquired by your user, acquired by user.",
            "To work simultaneously, user can execute labgrid-client -p bench allow testhost/tester",
        ),
        (
            "other/tester",
            "get_acquired_place",
            "place bench is not acquired on this computer, acquired on other.",
            "To allow this host, use labgrid-client -p bench allow testhost/tester on the other host",
        ),
        (
            "other/user",
            "acquire_place",
            "Place bench is already acquired by other/user.",
            "To work simultaneously, user can execute 'labgrid-client -p bench allow testhost/tester' on other.",
        ),
        (
            "other/tester",
            "acquire_place",
            "You have already acquired place bench on other.",
            "To work simultaneously, execute 'labgrid-client -p bench allow testhost/tester' on other.",
        ),
        (
            "other/user",
            "release_place",
            "place bench is acquired by a different user (other/user)",
            ", use --kick if you are sure",
        ),
    ],
)
def test_session_ownership_errors_are_cli_independent(session, owner, operation, description, hint):
    place = session.places["bench"]
    place.acquired = owner
    with pytest.raises(UserError) as error:
        if operation == "get_acquired_place":
            session.get_acquired_place(place)
        else:
            run(session, getattr(session, operation)(place))
    assert error.value.args == (description,)
    expected_type = (
        session_module.PlaceReleasePermissionError
        if operation == "release_place"
        else session_module.PlaceHostMismatchError
        if owner == "other/tester"
        else session_module.PlaceUserMismatchError
    )
    assert type(error.value) is expected_type
    assert error.value.place_name == "bench"
    assert error.value.owner_host == "other"
    assert error.value.owner_user == owner.split("/")[1]
    cli = commands(session, "release" if operation == "release_place" else "acquire")
    with pytest.raises(UserError) as error:
        if operation == "get_acquired_place":
            cli.get_acquired_place()
        elif operation == "acquire_place":
            run(session, cli._acquire_place("bench"))
        else:
            run(session, cli._release_place("bench"))
    separator = "" if operation == "release_place" else " "
    assert error.value.args == (description + separator + hint,)
    assert "".join(traceback.format_exception(error.value)).count("Traceback (most recent call last):") == 1


@pytest.mark.parametrize(
    "selector, expected",
    [
        (None, session_module.MissingPlacePatternError),
        ("missing", session_module.PlaceNotFoundError),
        ("+missing", session_module.PlaceNotFoundError),
        ("ben", session_module.AmbiguousPlaceError),
    ],
)
def test_typed_lookup_errors(session, selector, expected):
    session.places["bench2"] = Place("bench2")
    with pytest.raises(expected) as error:
        session.get_place(selector)
    assert isinstance(error.value, UserError)


def test_typed_place_preconditions(session):
    place = session.places["bench"]
    with pytest.raises(session_module.PlaceNotAcquiredError):
        session.get_acquired_place(place)
    with pytest.raises(session_module.PlaceNotAcquiredError):
        run(session, session.release_place(place))
    place.acquired = "testhost/tester"
    with pytest.raises(session_module.PlaceNotIdleError):
        session.get_idle_place(place)
    with pytest.raises(session_module.PlaceAlreadyAcquiredError):
        run(session, session.acquire_place(place))


def test_typed_invalid_inputs(session):
    place = session.places["bench"]
    with pytest.raises(session_module.InvalidTagError):
        run(session, session.set_tags(place, [Tag("?bad", "value")]))
    with pytest.raises(session_module.InvalidReservationFilterError):
        run(session, session.create_reservation([ReservationFilter("main", (Tag("?bad", "value"),))]))
    with pytest.raises(session_module.InvalidResourceMatchError):
        run(session, session.add_match(place, ResourceMatch("*", "group", "cls", rename="named")))
    place.matches = [ResourceMatch("missing", "group", "cls")]
    with pytest.raises(session_module.UnmatchedResourceError):
        run(session, session.acquire_place(place))
    place.acquired = "testhost/tester"
    with pytest.raises(session_module.InvalidClientIdentityError):
        run(session, session.allow(place, "missing-host"))


@pytest.mark.parametrize("operation", ["acquire", "access", "create", "release"])
def test_cli_does_not_add_hints_to_unrelated_user_errors(session, operation):
    place = session.places["bench"]
    place.acquired = "other/user"
    error = UserError("unrelated validation failure")
    cli = commands(session, "acquire")
    if operation == "access":
        session.get_acquired_place = MagicMock(side_effect=error)
        with pytest.raises(UserError) as caught:
            cli.get_acquired_place()
    else:
        method = {"acquire": "acquire_place", "create": "add_place", "release": "release_place"}[operation]
        setattr(session, method, AsyncMock(side_effect=error))
        cli.args.kick = False
        call = {
            "acquire": lambda: cli._acquire_place("bench"),
            "create": cli.add_place,
            "release": lambda: cli._release_place("bench"),
        }[operation]
        with pytest.raises(UserError) as caught:
            run(session, call())
    assert caught.value is error


def test_ownership_error_captures_owner_before_cache_changes(session):
    place = session.places["bench"]
    place.acquired = "other/user"
    with pytest.raises(session_module.PlaceUserMismatchError) as caught:
        session.get_acquired_place(place)
    place.acquired = None
    assert caught.value.owner_host == "other"
    assert caught.value.owner_user == "user"


def test_explicit_lookup_and_identity(session, monkeypatch):
    monkeypatch.setenv("LG_USERNAME", "other")
    monkeypatch.setenv("LG_HOSTNAME", "other")
    monkeypatch.setenv("LG_TOKEN", "wrong")
    place = session.places["bench"]
    place.aliases.add("tester:mine")
    place.reservation = "test-token"
    session.token = "test-token"
    assert session.get_place("mine") is place
    assert session.get_place("+") is place
    assert session.get_place(place) is place
    assert session.getuser() == "tester"
    assert session.gethostname() == "testhost"
    assert session.list_places() == (place,)
    assert session.list_places(acquired=True) == ()
    assert session.list_places(released=True) == (place,)


def test_acquire_and_release_return_synchronized_live_place(session, capsys):
    place = session.places["bench"]

    async def sync():
        place.acquired = "testhost/tester" if place.acquired is None else None
        return True

    session.sync_with_coordinator.side_effect = sync
    assert run(session, session.acquire_place(place)) is place
    assert place.acquired == "testhost/tester"
    assert run(session, session.release_place(place)) is place
    assert place.acquired is None
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("via_cli", [False, True], ids=["session", "cli"])
def test_acquire_resolved_place_ignores_conflicting_alias(session, via_cli):
    place = session.places["bench"]
    place.aliases.add("shortcut")
    session.places["other"] = Place("other", aliases={"tester:bench"})
    resolved = session.get_place("shortcut")
    assert resolved is place

    if via_cli:
        cli = commands(session, "acquire")
        run(session, cli._acquire_place("shortcut"))
    else:
        run(session, session.acquire_place(resolved))

    session.stub.AcquirePlace.assert_awaited_once_with(pb2.AcquirePlaceRequest(placename="bench"))


def test_resolved_deleted_place_does_not_match_another_place(session):
    deleted = session.places.pop("bench")
    session.places["bench2"] = Place("bench2")
    with pytest.raises(session_module.PlaceNotFoundError):
        session.get_place(deleted)


@pytest.mark.parametrize("operation", ["acquire", "create", "release", "tags"])
def test_place_mutation_reports_stream_loss_before_cache_update(session, operation):
    # Exercise real synchronization after the update stream ends while the
    # independent mutation RPC is still in flight.
    session.sync_with_coordinator = ClientSession.sync_with_coordinator.__get__(session)

    async def stream():
        yield pb2.ClientOutMessage()

    session.stub.ClientStream.return_value = stream()

    async def finish_rpc_after_stream_loss(request):
        await session._message_pump()
        assert session.stopping.is_set()

    if operation == "acquire":
        rpc = session.stub.AcquirePlace
        mutation = session.acquire_place(session.places["bench"])
    elif operation == "create":
        rpc = session.stub.AddPlace
        mutation = session.add_place("new-bench")
    elif operation == "release":
        session.places["bench"].acquired = "testhost/tester"
        rpc = session.stub.ReleasePlace
        mutation = session.release_place(session.places["bench"])
    else:
        rpc = session.stub.SetPlaceTags
        mutation = session.set_tags(session.places["bench"], [Tag("board", "test")])
    rpc.side_effect = finish_rpc_after_stream_loss

    with pytest.raises(ServerError):
        run(session, asyncio.wait_for(mutation, timeout=1.0))

    rpc.assert_awaited_once()


def test_place_mutation_reports_stream_loss_while_waiting_for_sync(session):
    session.sync_with_coordinator = ClientSession.sync_with_coordinator.__get__(session)
    pending = []

    class Stream:
        def cancel(self):
            pass

        async def __aiter__(self):
            yield pb2.ClientOutMessage()
            message = await session.out_queue.get()
            if message is not None and message.HasField("sync"):
                event = session.sync_events[message.sync.id]
                pending.append((event, event.is_set()))
            # End the stream without acknowledging the synchronization request.

    session.stub.ClientStream.return_value = Stream()

    async def exercise():
        session.pump_task = session.loop.create_task(session._message_pump())
        try:
            with pytest.raises(ServerError, match="Could not synchronize place mutation"):
                await asyncio.wait_for(session.acquire_place(session.places["bench"]), timeout=1.0)
            (event, was_set), = pending
            assert not was_set
            assert event.is_set()
            assert session.stopping.is_set()
            assert not session.sync_events
            session.stub.AcquirePlace.assert_awaited_once_with(pb2.AcquirePlaceRequest(placename="bench"))
        finally:
            await asyncio.wait_for(session.stop(), timeout=1.0)

    run(session, exercise())


def test_reservation_domain_results(session, capsys):
    message = reservation_message()
    session.stub.CreateReservation.return_value = pb2.CreateReservationResponse(reservation=message)
    session.stub.PollReservation.return_value = pb2.PollReservationResponse(reservation=message)
    session.stub.GetReservations.return_value = pb2.GetReservationsResponse(reservations=[message])
    result = run(session, session.create_reservation((ReservationFilter("main", (Tag("board", "test"),)),), 2.0))
    assert isinstance(result, Reservation)
    assert result.token == message.token
    request = session.stub.CreateReservation.call_args.args[0]
    assert dict(request.filters["main"].filter) == {"board": "test"}
    assert request.prio == 2.0
    assert run(session, session.poll_reservation(result)).state is ReservationState.allocated
    assert run(session, session.wait_reservation(result)).token == message.token
    assert isinstance(run(session, session.list_reservations())[0], Reservation)
    assert run(session, session.cancel_reservation(result)) is None
    assert session.stub.CancelReservation.call_args.args[0].token == message.token
    assert capsys.readouterr() == ("", "")


def test_wait_reservation_polls_waiting_state(session, monkeypatch):
    waiting = reservation_message()
    waiting.state = ReservationState.waiting.value
    session.stub.PollReservation.side_effect = [
        pb2.PollReservationResponse(reservation=waiting),
        pb2.PollReservationResponse(reservation=reservation_message()),
    ]
    sleep = AsyncMock()
    monkeypatch.setattr(session_module.asyncio, "sleep", sleep)
    assert run(session, session.wait_reservation("test-token")).state is ReservationState.allocated
    sleep.assert_awaited_once_with(1.0)


def test_wait_reservation_synchronizes_pending_place_updates(session):
    session.sync_with_coordinator = ClientSession.sync_with_coordinator.__get__(session)
    session.stub.PollReservation.return_value = pb2.PollReservationResponse(reservation=reservation_message())
    allocated_place = session.places["bench"].as_pb2()
    allocated_place.reservation = "test-token"

    class Stream:
        def cancel(self):
            pass

        async def __aiter__(self):
            while True:
                message = await session.out_queue.get()
                if message is None:
                    return
                response = pb2.ClientOutMessage()
                response.updates.add().place.CopyFrom(allocated_place)
                response.sync.id = message.sync.id
                yield response

    session.stub.ClientStream.return_value = Stream()

    async def exercise():
        session.pump_task = session.loop.create_task(session._message_pump())
        try:
            result = await session.wait_reservation("test-token")
            assert result.state is ReservationState.allocated
            assert session.get_place("+" + result.token) is session.places["bench"]
        finally:
            await session.stop()

    run(session, asyncio.wait_for(exercise(), timeout=1.0))


def test_wait_reservation_reports_failed_synchronization(session):
    session.stub.PollReservation.return_value = pb2.PollReservationResponse(reservation=reservation_message())
    session.sync_with_coordinator.return_value = False
    with pytest.raises(ServerError):
        run(session, session.wait_reservation("test-token"))


def test_wait_reservation_reports_stream_stopping_during_poll(session):
    session.sync_with_coordinator = ClientSession.sync_with_coordinator.__get__(session)

    class Stream:
        def cancel(self):
            pass

        async def __aiter__(self):
            yield pb2.ClientOutMessage()

    session.stub.ClientStream.return_value = Stream()

    async def poll(request):
        # The update stream ends while the independent unary RPC is in flight.
        await session._message_pump()
        return pb2.PollReservationResponse(reservation=reservation_message())

    session.stub.PollReservation.side_effect = poll
    with pytest.raises(ServerError, match="Could not synchronize reservation"):
        run(session, asyncio.wait_for(session.wait_reservation("test-token"), timeout=1.0))

    assert session.stopping.is_set()
    assert not session.sync_events
    assert session.out_queue.get_nowait() is None
    assert session.out_queue.empty()


@pytest.mark.parametrize("pattern", ["*/group/SerialPort", "exporter/group/SerialPort"])
def test_add_match_reuses_unnamed_cached_matches(session, pattern):
    session.places["source"] = Place.from_pb2(
        pb2.Place(name="source", matches=[ResourceMatch.fromstr(pattern).as_pb2()])
    )
    match = session.get_place("source").matches[0]
    place = session.places["bench"]

    assert run(session, session.add_match(place, match)) is True
    request = session.stub.AddPlaceMatch.call_args.args[0]
    assert request.pattern == pattern
    assert not request.HasField("rename")

    place.matches.append(match)
    assert run(session, session.add_match(place, match)) is False
    session.stub.AddPlaceMatch.assert_awaited_once()


def test_tags_and_matches_use_domain_inputs(session):
    place = session.places["bench"]
    run(session, session.set_tags(place, [Tag("board", "test")]))
    assert dict(session.stub.SetPlaceTags.call_args.args[0].tags) == {"board": "test"}
    match = ResourceMatch.fromstr("exporter/group/SerialPort")
    assert run(session, session.add_match(place, match)) is True
    assert session.stub.AddPlaceMatch.call_args.args[0].pattern == "exporter/group/SerialPort"
    place.matches.append(match)
    assert run(session, session.add_match(place, match)) is False
    run(session, session.del_match(place, match))
    assert session.stub.DeletePlaceMatch.call_args.args[0].pattern == repr(match)


def test_acquisition_ownership_checks(session):
    place = session.places["bench"]
    place.acquired = "other/user"
    with pytest.raises(UserError, match="already acquired"):
        run(session, session.acquire_place(place))
    with pytest.raises(UserError, match="different user"):
        run(session, session.release_place(place))
    session.stub.AcquirePlace.assert_not_awaited()
    session.stub.ReleasePlace.assert_not_awaited()


def test_rpc_error_is_domain_error(session):
    error = grpc.aio.AioRpcError(grpc.StatusCode.UNAVAILABLE, None, None, "offline")
    session.stub.AcquirePlace.side_effect = error
    with pytest.raises(ServerError, match="offline"):
        run(session, session.acquire_place(session.places["bench"]))


def test_typed_target_resources_keep_live_entries(session):
    place = session.places["bench"]
    place.acquired = "testhost/tester"
    place.matches = [ResourceMatch("exporter", "group", "SerialPort", rename="console")]
    place.acquired_resources = [("exporter", "group", "SerialPort", "port")]
    resource = ResourceEntry({"cls": "SerialPort", "params": {"port": "unused"}})
    session.resources = {"exporter": {"group": {"port": resource}}}
    (binding,) = session.get_target_resources(place)
    assert binding.name == "console"
    assert binding.resource is resource


def test_get_target_resolves_each_places_configured_role(session, tmp_path, monkeypatch):
    monkeypatch.setattr(ResourceManager, "instances", {})
    config = tmp_path / "environment.yaml"
    config.write_text(
        "targets:\n"
        "  first:\n"
        "    resources:\n"
        "      RemotePlace:\n"
        "        name: bench\n"
        "  second:\n"
        "    resources:\n"
        "      RemotePlace:\n"
        "        name: bench2\n"
    )
    session.env = Environment(str(config))
    first_place = session.places["bench"]
    second_place = session.places["bench2"] = Place("bench2")
    for place in (first_place, second_place):
        place.acquired = "testhost/tester"

    first_target = session.get_target(first_place)
    assert first_target.name == "first"
    assert first_target.get_resource(RemotePlace).name == "bench"

    second_target = session.get_target(second_place)
    assert second_target.name == "second"
    assert second_target.get_resource(RemotePlace).name == "bench2"
    assert second_target is not first_target
    assert session.role is None

    session.role = "first"
    assert session.get_target(second_place) is first_target


def test_recreated_resource_event_has_no_previous_snapshot(session):
    events = []
    session.subscribe(events.append)
    data = {"cls": "SerialPort", "params": {}, "avail": True}

    run(session, session._on_resource_changed("exporter", "group", "port", data.copy()))
    live = session.resources["exporter"]["group"]["port"]
    run(session, session._on_resource_changed("exporter", "group", "port", {}))
    run(session, session._on_resource_changed("exporter", "group", "port", data.copy()))

    created, deleted, recreated = events
    assert created.previous is None
    assert deleted.previous.cls == "SerialPort"
    assert deleted.current is None
    assert recreated.current.cls == "SerialPort"
    assert recreated.previous is None
    assert session.resources["exporter"]["group"]["port"] is live
    assert live.cls == "SerialPort"
    assert recreated.current is not live


def test_update_events_preserve_cache_identity_and_snapshots(session, capsys):
    events = []
    session.subscribe(events.append)
    resource = {"cls": "SerialPort", "params": {}, "avail": True}
    run(session, session._on_resource_changed("exporter", "group", "port", resource))
    live = session.resources["exporter"]["group"]["port"]
    run(session, session._on_resource_changed("exporter", "group", "port", {**resource, "avail": False}))
    assert session.resources["exporter"]["group"]["port"] is live
    assert events[0].current.avail is True
    assert events[1].previous.avail is True
    assert live.avail is False
    run(session, session._on_resource_changed("exporter", "group", "port", {}))
    assert events[-1].current is None
    place = session.places["bench"]
    run(session, session._on_place_changed(pb2.Place(name="bench", comment="new")))
    assert session.places["bench"] is place
    assert events[-1].previous.comment == ""
    assert events[-1].current.comment == "new"
    run(session, session._on_place_deleted("bench"))
    assert events[-1].current is None
    assert capsys.readouterr() == ("", "")


def test_monitor_presenter_preserves_text(session, capsys):
    cli = commands(session, "monitor")
    session.subscribe(cli._print_event)
    message = pb2.Place(name="new")
    run(session, session._on_place_changed(message))
    assert capsys.readouterr().out == f"Place new created: {message}\n"
    message.comment = "changed"
    run(session, session._on_place_changed(message))
    assert capsys.readouterr().out == "Place new changed:\n  comment:  -> changed\n"
    run(session, session._on_place_deleted("new"))
    assert capsys.readouterr().out == "Place new deleted\n"
    data = {"cls": "SerialPort", "params": {}, "acquired": None, "avail": True}
    run(session, session._on_resource_changed("ex", "g", "r", data.copy()))
    assert capsys.readouterr().out == f"Resource ex/g/SerialPort/r created: {data}\n"
    run(session, session._on_resource_changed("ex", "g", "r", {**data, "avail": False}))
    assert capsys.readouterr().out == "Resource ex/g/SerialPort/r changed:\n  avail: True -> False\n"
    run(session, session._on_resource_changed("ex", "g", "r", {}))
    assert capsys.readouterr().out == "Resource ex/g/???/r deleted\n"


@pytest.mark.parametrize(
    "arguments, expected",
    [
        (["acquire"], "acquired place bench\n"),
        (["places"], f"{'bench':<40s} \n"),
        (["release"], "released place bench\n"),
        (["release", "--kick"], "warning: kicking user (other/user)\nreleased place bench\n"),
        (["allow", "other/user"], "allowed other/user for place bench\n"),
    ],
)
def test_cli_operation_output(session, capsys, arguments, expected):
    if arguments[0] in ("release", "allow"):
        session.places["bench"].acquired = "other/user" if "--kick" in arguments else "testhost/tester"
    cli = commands(session, *arguments)
    run(session, cli.args.func(cli))
    assert capsys.readouterr() == (expected, "")


def test_cli_skip_match_messages(session, capsys):
    session.places["bench"].matches = [ResourceMatch.fromstr("e/g/c")]
    cli = commands(session, "add-match", "e/g/c")
    run(session, cli.add_match())
    assert capsys.readouterr() == ("", "pattern 'e/g/c' exists, skipping\n")
    session.stub.AddPlaceMatch.assert_not_awaited()
    cli = commands(session, "del-match", "other/g/c")
    run(session, cli.del_match())
    assert capsys.readouterr() == ("", "pattern 'other/g/c' not found, skipping\n")
    session.stub.DeletePlaceMatch.assert_awaited_once()


def test_cli_shell_reservation_output(session, capsys):
    session.stub.CreateReservation.return_value = pb2.CreateReservationResponse(reservation=reservation_message())
    cli = commands(session, "reserve", "--shell", "board=test")
    run(session, cli.create_reservation())
    assert capsys.readouterr() == ("export LG_TOKEN=test-token\n", "")


@pytest.mark.parametrize(
    "arguments, expected",
    [
        (["set-tags", "broken"], "tag 'broken' needs to match '<key>=<value>'"),
        (["reserve", "broken"], "'broken' is not a valid filter (must contain a '=')"),
        (["add-match", "broken"], "invalid pattern format 'broken' (use 'exporter/group/cls/name')"),
    ],
)
def test_cli_validation_messages(session, arguments, expected):
    cli = commands(session, *arguments)
    with pytest.raises(UserError) as error:
        run(session, cli.args.func(cli))
    assert error.value.args == (expected,)


def test_cli_main_dispatch_and_exit_status(session, monkeypatch, capsys):
    monkeypatch.setattr(client, "start_session", lambda *args, **kwargs: session)
    monkeypatch.setattr(client.signal, "signal", lambda *args: None)
    monkeypatch.setattr(client.asyncio, "new_event_loop", lambda: session.loop)
    session.stop = AsyncMock()
    monkeypatch.setattr(client.sys, "argv", ["labgrid-client", "-p", "bench", "acquire"])
    for name in ("LG_ENV", "LG_STATE", "STATE", "LG_INITIAL_STATE"):
        monkeypatch.delenv(name, raising=False)
    with monkeypatch.context() as cli_patches:
        # Keep the fixture's loop usable until teardown, then restore real close.
        cli_patches.setattr(session.loop, "close", lambda: None)
        with pytest.raises(SystemExit) as result:
            client.main()
    assert result.value.code == 0
    assert capsys.readouterr() == ("acquired place bench\n", "")
    session.stop.assert_awaited_once()


def test_cli_multi_place_acquisition_continues_after_error(session, capsys):
    session.places["busy"] = Place("busy", acquired="other/user")
    cli = commands(session, "acquire")
    cli.env = MagicMock()
    cli.get_place_names_from_env = lambda: ["busy", "bench"]
    with pytest.raises(UserError, match="already acquired"):
        run(session, cli.acquire())
    assert capsys.readouterr().out == "acquired place bench\n"


def test_stop_before_start(session):
    run(session, session.stop())
    assert session.stopping.is_set()


def test_start_stream_sync_and_shutdown_without_network(session):
    session.sync_with_coordinator = ClientSession.sync_with_coordinator.__get__(session)
    sent = []

    class Stream:
        def cancel(self):
            pass

        async def __aiter__(self):
            while True:
                message = await session.out_queue.get()
                if message is None:
                    return
                sent.append(message)
                if message.HasField("sync"):
                    response = pb2.ClientOutMessage()
                    response.sync.id = message.sync.id
                    yield response

    session.stub.ClientStream.return_value = Stream()

    async def exercise():
        try:
            await asyncio.wait_for(session.start(), timeout=1.0)
            assert sent[0].startup.name == "testhost/tester"
            assert sent[1].subscribe.all_places
            assert sent[2].subscribe.all_resources
            assert session.sync_events == {}
        finally:
            await asyncio.wait_for(session.stop(), timeout=1.0)

    run(session, exercise())
    assert session.pump_task.done()
    assert session.stopping.is_set()


def test_monitor_unsubscribes_when_cancelled(session):
    cli = commands(session, "monitor")

    async def exercise():
        task = asyncio.create_task(cli.do_monitor())
        await asyncio.sleep(0)
        assert cli._print_event in session._listeners
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert cli._print_event not in session._listeners

    run(session, exercise())


def test_listener_failure_does_not_interrupt_updates(session, caplog):
    def broken(event):
        raise ValueError("listener failed")

    events = []
    session.subscribe(broken)
    session.subscribe(events.append)
    run(session, session._on_place_changed(pb2.Place(name="new")))
    assert events[0].current.name == "new"
    assert "session event listener failed" in caplog.text


def test_monitor_broken_pipe_stops_stream_and_releases_waiters(session, monkeypatch, caplog):
    cli = commands(session, "monitor")
    monkeypatch.setattr(client, "print", MagicMock(side_effect=BrokenPipeError("closed stdout")), raising=False)
    consumed = []

    async def stream():
        for name in ("first", "second"):
            consumed.append(name)
            message = pb2.ClientOutMessage()
            message.updates.add().place.CopyFrom(pb2.Place(name=name))
            yield message

    session.stub.ClientStream.return_value = stream()

    async def exercise():
        pending_sync = session.sync_events[1] = asyncio.Event()
        monitor = asyncio.create_task(cli.do_monitor())
        try:
            await asyncio.sleep(0)
            await session._message_pump()
            await monitor
            assert session.stopping.is_set()
            assert pending_sync.is_set()
            assert not session.sync_events
            assert cli._print_event not in session._listeners
        finally:
            monitor.cancel()

    run(session, asyncio.wait_for(exercise(), timeout=1.0))
    assert consumed == ["first"]
    assert "error in coordinator message pump task" in caplog.text
    assert "session event listener failed" not in caplog.text


def test_failed_start_closes_channel(session, monkeypatch):
    session.start = AsyncMock(side_effect=ServerError("unreachable"))
    session.stop = AsyncMock()
    monkeypatch.setattr(session_module, "ClientSession", lambda *args, **kwargs: session)
    with pytest.raises(ServerError):
        session_module.start_session("localhost", loop=session.loop)
    session.stop.assert_awaited_once()
    session.channel.close.assert_awaited_once()


def test_legacy_connection_helper_resolves_cli_defaults(monkeypatch):
    monkeypatch.setenv("LG_USERNAME", "tester")
    monkeypatch.setenv("LG_HOSTNAME", "testhost")
    monkeypatch.setenv("LG_TOKEN", "test-token")
    start = MagicMock()
    monkeypatch.setattr(client, "start_library_session", start)
    client.start_session("unused", extra={"args": object(), "prog": "labgrid-client", "role": "main"})
    options = start.call_args.kwargs
    assert options["username"] == "tester"
    assert options["hostname"] == "testhost"
    assert options["token"] == "test-token"
    assert options["role"] == "main"
    assert "args" not in options
    assert "prog" not in options
