"""Reusable coordinator session, independent of command-line presentation."""

from __future__ import annotations

import asyncio
import copy
import itertools
import logging
from collections.abc import Callable, Sequence
from contextvars import ContextVar
from dataclasses import dataclass
from getpass import getuser
from socket import gethostname

import attr
import grpc
from exceptiongroup import ExceptionGroup

from .. import Environment, Target, target_factory
from ..resource.remote import RemotePlace, RemotePlaceManager
from ..util import labgrid_version
from ..util.proxy import proxymanager
from .common import (
    TAG_KEY,
    TAG_VAL,
    Place,
    Reservation,
    ReservationState,
    ResourceEntry,
    ResourceMatch,
    queue_as_aiter,
)
from .generated import labgrid_coordinator_pb2, labgrid_coordinator_pb2_grpc


class Error(Exception):
    def __str__(self):
        return f"Error: {' '.join(self.args)}"


class UserError(Error):
    """Base class for invalid requests and unmet operation preconditions."""


class MissingPlaceNameError(UserError):
    """Creating a place requires a name."""


class MissingPlacePatternError(UserError):
    """Looking up a place requires a selector."""


class PlaceNotFoundError(UserError):
    """The selector or reservation token does not match a place."""


class AmbiguousPlaceError(UserError):
    """The selector matches more than one place."""


class PlaceNotAcquiredError(UserError):
    """The operation requires an acquired place."""


class PlaceNotIdleError(UserError):
    """The operation requires an idle place."""


class PlaceAlreadyAcquiredError(UserError):
    """The current client already owns the requested place."""


class PlaceOwnershipError(UserError):
    """An ownership conflict, with the owner captured when validation failed."""

    def __init__(self, message: str, place: Place):
        super().__init__(message)
        self.place_name = place.name
        self.owner_host, self.owner_user = place.acquired.split("/")


class PlaceUserMismatchError(PlaceOwnershipError):
    """The place belongs to another user."""


class PlaceHostMismatchError(PlaceOwnershipError):
    """The place belongs to this user on another host."""


class PlaceReleasePermissionError(PlaceOwnershipError):
    """Releasing another user's place requires explicit override permission."""


class InvalidTagError(UserError):
    """A tag key or value is invalid."""


class InvalidReservationFilterError(UserError):
    """A reservation filter contains an invalid criterion."""


class InvalidResourceMatchError(UserError):
    """A resource match is invalid for the requested operation."""


class UnmatchedResourceError(UserError):
    """A configured match has no corresponding remote resource."""


class InvalidClientIdentityError(UserError):
    """A client identity does not contain the required host and username."""


class ServerError(Error):
    pass


class ErrorGroup(ExceptionGroup):
    def __str__(self):
        errors_combined = "\n".join(f"- {' '.join(e.args)}" for e in self.exceptions)
        return f"{self.message}:\n{errors_combined}"


@dataclass(frozen=True)
class Tag:
    """A place tag or reservation filter criterion."""

    key: str
    value: str


@dataclass(frozen=True)
class ReservationFilter:
    """A named set of reservation criteria."""

    name: str
    tags: tuple[Tag, ...]


@dataclass(frozen=True)
class TargetResource:
    """A matched resource and its local binding name."""

    name: str
    resource: ResourceEntry


@dataclass(frozen=True)
class ResourceChanged:
    """Snapshots before and after a resource update; None denotes absence."""

    exporter: str
    group: str
    name: str
    previous: ResourceEntry | None
    current: ResourceEntry | None


@dataclass(frozen=True)
class PlaceChanged:
    """Place update snapshots, with the original creation description for CLI compatibility."""

    name: str
    previous: Place | None
    current: Place | None
    description: str = ""


SessionEvent = ResourceChanged | PlaceChanged


@attr.s(eq=False)
class ClientSession:
    """Coordinator connection and domain operations without terminal side effects.

    Place and resource lookups return live cached objects. Mutations synchronize
    the cache before returning; callers must not mutate these objects themselves.
    Event callbacks receive independent snapshots and run synchronously in update
    order. Callback failures are logged without terminating the update stream,
    except BrokenPipeError, which propagates to stop the stream.
    """

    address: str = attr.ib(validator=attr.validators.instance_of(str))
    credentials: grpc.ChannelCredentials | None = attr.ib(default=None, kw_only=True)
    loop: asyncio.AbstractEventLoop = attr.ib()
    env: Environment | None = attr.ib(default=None)
    role: str | None = attr.ib(default=None)
    username: str | None = attr.ib(default=None, kw_only=True)
    hostname: str | None = attr.ib(default=None, kw_only=True)
    token: str | None = attr.ib(default=None, kw_only=True)

    def gethostname(self) -> str:
        """Return the explicit client host identity or the local hostname."""
        return self.hostname if self.hostname is not None else gethostname()

    def getuser(self) -> str:
        """Return the explicit client user identity or the local username."""
        return self.username if self.username is not None else getuser()

    def __attrs_post_init__(self):
        """Actions which are executed if a connection is successfully opened."""
        self.stopping = asyncio.Event()
        self.resources = {}
        self.places = {}
        self._listeners = []

        # It seems since https://github.com/grpc/grpc/pull/34647, the
        # ping_timeout_ms default of 60 seconds overrides keepalive_timeout_ms,
        # so set it as well.
        # Use GRPC_VERBOSITY=DEBUG GRPC_TRACE=http_keepalive for debugging.
        channel_options = [
            ("grpc.keepalive_time_ms", 7500),  # 7.5 seconds
            ("grpc.keepalive_timeout_ms", 10000),  # 10 seconds
            ("grpc.http2.ping_timeout_ms", 10000),  # 10 seconds
            ("grpc.http2.max_pings_without_data", 0),  # no limit
        ]

        if self.credentials:
            self.channel = grpc.aio.secure_channel(
                target=self.address,
                credentials=self.credentials,
                options=channel_options,
            )
        else:
            self.channel = grpc.aio.insecure_channel(
                target=self.address,
                options=channel_options,
            )

        self.stub = labgrid_coordinator_pb2_grpc.CoordinatorStub(self.channel)

        self.out_queue = asyncio.Queue()
        self.stream_call = None
        self.pump_task = None
        self.sync_id = itertools.count(start=1)
        self.sync_events = {}

        self.logger = logging.getLogger("ClientSession")

    async def start(self) -> None:
        """Starts receiving resource and place updates from the coordinator."""
        self.resources = {}
        self.places = {}

        self.pump_task = self.loop.create_task(self._message_pump())
        msg = labgrid_coordinator_pb2.ClientInMessage()
        msg.startup.version = labgrid_version()
        msg.startup.name = f"{self.gethostname()}/{self.getuser()}"
        self.out_queue.put_nowait(msg)
        msg = labgrid_coordinator_pb2.ClientInMessage()
        msg.subscribe.all_places = True
        self.out_queue.put_nowait(msg)
        msg = labgrid_coordinator_pb2.ClientInMessage()
        msg.subscribe.all_resources = True
        self.out_queue.put_nowait(msg)
        await self.sync_with_coordinator()
        if self.stopping.is_set():
            raise ServerError("Could not connect to coordinator")

    async def stop(self) -> None:
        """Stops stream for resource and place updates started with ClientSession.start()."""
        self.out_queue.put_nowait(None)  # let the sender side exit gracefully
        if self.stream_call:
            self.stream_call.cancel()
        try:
            if self.pump_task is not None:
                await self.pump_task
        except asyncio.CancelledError:
            pass
        self.stopping.set()
        self._cancel_pending_syncs()

    async def close(self) -> None:
        """Closes the channel to the coordinator."""
        await self.channel.close()

    async def sync_with_coordinator(self) -> bool:
        """Wait for coordinator to process all previous messages in stream."""
        if self.stopping.is_set():
            return False
        identifier = next(self.sync_id)
        event = self.sync_events[identifier] = asyncio.Event()
        msg = labgrid_coordinator_pb2.ClientInMessage()
        msg.sync.id = identifier
        self.logger.debug("sending sync %s", identifier)
        self.out_queue.put_nowait(msg)
        await event.wait()
        if self.stopping.is_set():
            self.logger.debug("sync %s failed", identifier)
        else:
            self.logger.debug("received sync %s", identifier)
        return not self.stopping.is_set()

    def _cancel_pending_syncs(self):
        """Cancel all pending ClientSession.sync_with_coordinator() calls."""
        assert self.stopping.is_set()  # only call when something has gone wrong
        while True:
            try:
                identifier, event = self.sync_events.popitem()
                self.logger.debug("cancelling %s %s", identifier, event)
                event.set()
            except KeyError:
                break

    async def _message_pump(self):
        """Task for receiving resource and place updates."""
        got_message = False
        try:
            self.stream_call = call = self.stub.ClientStream(queue_as_aiter(self.out_queue, self.logger))
            async for out_msg in call:
                out_msg: labgrid_coordinator_pb2.ClientOutMessage
                got_message = True
                self.logger.debug("out_msg from coordinator: %s", out_msg)
                for update in out_msg.updates:
                    update_kind = update.WhichOneof("kind")
                    if update_kind == "resource":
                        resource: labgrid_coordinator_pb2.Resource = update.resource
                        await self._on_resource_changed(
                            resource.path.exporter_name,
                            resource.path.group_name,
                            resource.path.resource_name,
                            ResourceEntry.data_from_pb2(resource),
                        )
                    elif update_kind == "del_resource":
                        resource_path: labgrid_coordinator_pb2.Resource.Path = update.del_resource
                        await self._on_resource_changed(
                            resource_path.exporter_name, resource_path.group_name, resource_path.resource_name, {}
                        )
                    elif update_kind == "place":
                        place = update.place
                        await self._on_place_changed(place)
                    elif update_kind == "del_place":
                        place_name = update.del_place
                        await self._on_place_deleted(place_name)
                    else:
                        self.logger.warning("unknown update from coordinator! %s", update_kind)
                if out_msg.HasField("sync"):
                    event = self.sync_events.pop(out_msg.sync.id)
                    event.set()
        except grpc.aio.AioRpcError as e:
            if e.code() == grpc.StatusCode.UNAVAILABLE:
                if got_message:
                    self.logger.error("coordinator became unavailable: %s", e.details())
                else:
                    self.logger.error("coordinator is unavailable: %s", e.details())
            else:
                self.logger.exception("unexpected grpc error in coordinator message pump task")
        except Exception:
            self.logger.exception("error in coordinator message pump task")
        finally:
            self.stopping.set()
            self.out_queue.put_nowait(None)  # let the sender side exit gracefully
            self._cancel_pending_syncs()

    def subscribe(self, callback: Callable[[SessionEvent], None]) -> None:
        """Register an ordered update listener."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def unsubscribe(self, callback: Callable[[SessionEvent], None]) -> None:
        """Remove a previously registered listener."""
        self._listeners.remove(callback)

    def _emit(self, event: SessionEvent) -> None:
        for callback in tuple(self._listeners):
            try:
                callback(event)
            except BrokenPipeError:
                raise
            except Exception:
                self.logger.exception("session event listener failed")

    async def _on_resource_changed(self, exporter, group_name, resource_name, resource):
        group = self.resources.setdefault(exporter, {}).setdefault(group_name, {})
        previous = group.get(resource_name)
        old = copy.deepcopy(previous) if previous is not None and "cls" in previous.data else None
        if resource_name not in group:
            group[resource_name] = ResourceEntry(resource)
        else:
            group[resource_name].data = resource
        current = copy.deepcopy(group[resource_name]) if "cls" in resource else None
        self._emit(ResourceChanged(exporter, group_name, resource_name, old, current))

    async def _on_place_changed(self, place_pb2):
        name = place_pb2.name
        old = copy.deepcopy(self.places.get(name))
        if name not in self.places:
            self.places[name] = Place.from_pb2(place_pb2)
        else:
            self.places[name].update_from_pb2(place_pb2)
        self._emit(PlaceChanged(name, old, copy.deepcopy(self.places[name]), str(place_pb2)))

    async def _on_place_deleted(self, name: str) -> None:
        old = self.places.pop(name)
        self._emit(PlaceChanged(name, copy.deepcopy(old), None))

    def list_places(self, acquired: bool = False, released: bool = False) -> tuple[Place, ...]:
        """Return live places matching the requested acquisition state."""
        return tuple(
            p for p in self.places.values() if not (acquired and p.acquired is None) and not (released and p.acquired)
        )

    def _match_places(self, pattern):
        """search for substring matches of pattern in place names and aliases

        Aliases in the format "namespace:alias" only match if the namespace is
        the current user name.
        """
        result = set()

        # reservation token lookup
        token = None
        if pattern.startswith("+"):
            token = pattern[1:]
            if not token:
                token = self.token
            if not token:
                return []
            for name, place in self.places.items():
                if place.reservation == token:
                    result.add(name)
            if not result:
                raise PlaceNotFoundError(f"reservation token {token} matches nothing")
            return list(result)

        # name and alias lookup
        for name, place in self.places.items():
            if pattern in name:
                result.add(name)
            for alias in place.aliases:
                if ":" in alias:
                    namespace, alias = alias.split(":", 1)
                    if namespace != self.getuser():
                        continue
                    if alias == pattern:  # prefer user namespace
                        return [name]
                if pattern in alias:
                    result.add(name)
        return list(result)

    def _check_allowed(self, place):
        if not place.acquired:
            raise PlaceNotAcquiredError(f"place {place.name} is not acquired")
        if f"{self.gethostname()}/{self.getuser()}" not in place.allowed:
            host, user = place.acquired.split("/")
            if user != self.getuser():
                raise PlaceUserMismatchError(
                    f"place {place.name} is not acquired by your user, acquired by {user}.", place
                )
            if host != self.gethostname():
                raise PlaceHostMismatchError(
                    f"place {place.name} is not acquired on this computer, acquired on {host}.", place
                )

    def get_place(self, place: str | Place) -> Place:
        """Resolve a name, alias, reservation selector, or existing place."""
        if isinstance(place, Place):
            try:
                return self.places[place.name]
            except KeyError:
                raise PlaceNotFoundError(f"place {place.name} no longer exists") from None
        pattern = place
        if pattern is None:
            raise MissingPlacePatternError("place pattern not specified")
        places = self._match_places(pattern)
        if not places:
            raise PlaceNotFoundError(f"place pattern {pattern} matches nothing")
        if pattern in places:
            return self.places[pattern]
        if len(places) > 1:
            raise AmbiguousPlaceError(f"pattern {pattern} matches multiple places ({', '.join(places)})")
        return self.places[places[0]]

    def get_place_names_from_env(self) -> list[str]:
        """Returns a list of RemotePlace names found in the environment config."""
        places = []
        for role_config in self.env.config.get_targets().values():
            resources, _ = target_factory.normalize_config(role_config)
            remote_places = resources.get("RemotePlace", [])
            for place in remote_places:
                places.append(place)

        return places

    def get_idle_place(self, place: str | Place) -> Place:
        """Resolve a place and require that it is idle."""
        place = self.get_place(place)
        if place.acquired:
            err = "This operation requires the place to be idle."
            if place.acquired == self.gethostname() + "/" + self.getuser():
                raise PlaceNotIdleError(f"{err} Please release {place.name}.")
            else:
                raise PlaceNotIdleError(f"{err} Place {place.name} is acquired by {place.acquired}.")
        return place

    def get_acquired_place(self, place: str | Place) -> Place:
        """Resolve a place and require access for this client identity."""
        place = self.get_place(place)
        self._check_allowed(place)
        return place

    def check_matches(self, place: Place) -> None:
        """Require that every configured match has a corresponding resource."""
        resources = []
        for exporter, groups in self.resources.items():
            for group_name, group in groups.items():
                for resource_name, resource in group.items():
                    resource_path = (exporter, group_name, resource.cls, resource_name)
                    resources.append(resource_path)

        match = place.unmatched(resources)
        if match:
            raise UnmatchedResourceError(f"Match {match} has no matching remote resource")

    async def add_place(self, name: str) -> Place:
        """Add a place to the coordinator"""
        if not name:
            raise MissingPlaceNameError("missing place name")

        request = labgrid_coordinator_pb2.AddPlaceRequest(name=name)
        await self._mutation(self.stub.AddPlace, request)

        return self.places[name]

    async def del_place(self, place: Place) -> None:
        """Delete a place from the coordinator"""
        place = self.get_idle_place(place)
        request = labgrid_coordinator_pb2.DeletePlaceRequest(name=place.name)
        await self._mutation(self.stub.DeletePlace, request)

    async def add_alias(self, place: Place, alias: str) -> None:
        """Add an alias for a place on the coordinator"""
        place = self.get_idle_place(place)

        request = labgrid_coordinator_pb2.AddPlaceAliasRequest(placename=place.name, alias=alias)

        await self._mutation(self.stub.AddPlaceAlias, request)

    async def del_alias(self, place: Place, alias: str) -> None:
        """Delete an alias for a place from the coordinator"""
        place = self.get_idle_place(place)

        request = labgrid_coordinator_pb2.DeletePlaceAliasRequest(placename=place.name, alias=alias)

        await self._mutation(self.stub.DeletePlaceAlias, request)

    async def set_comment(self, place: Place, comment: str) -> None:
        """Set the comment on a place"""
        place = self.get_place(place)

        request = labgrid_coordinator_pb2.SetPlaceCommentRequest(placename=place.name, comment=comment)

        await self._mutation(self.stub.SetPlaceComment, request)

    async def release_from(self, place: Place, acquired: str) -> Place:
        """Release a place, but only if acquired by a specific user"""
        place = self.get_place(place)
        if not place.acquired:
            raise PlaceNotAcquiredError(f"place {place.name} is not acquired")

        request = labgrid_coordinator_pb2.ReleasePlaceRequest(placename=place.name, fromuser=acquired)

        await self._mutation(self.stub.ReleasePlace, request)

        return place

    async def allow(self, place: Place, user: str) -> None:
        """Allow another use access to a previously acquired place"""
        place = self.get_acquired_place(place)
        if "/" not in user:
            raise InvalidClientIdentityError(f"user {user} must be in <host>/<username> format")
        request = labgrid_coordinator_pb2.AllowPlaceRequest(placename=place.name, user=user)

        await self._mutation(self.stub.AllowPlace, request)

    async def set_tags(self, place: Place, tags: Sequence[Tag]) -> None:
        """Set or remove place tags (an empty value removes a tag)."""
        place = self.get_place(place)
        values = {}
        for tag in tags:
            if not TAG_KEY.match(tag.key):
                raise InvalidTagError(f"tag key '{tag.key}' needs to match the rexex '{TAG_KEY.pattern}'")
            if not TAG_VAL.match(tag.value):
                raise InvalidTagError(f"tag value '{tag.value}' needs to match the rexex '{TAG_VAL.pattern}'")
            values[tag.key] = tag.value
        await self._mutation(
            self.stub.SetPlaceTags, labgrid_coordinator_pb2.SetPlaceTagsRequest(placename=place.name, tags=values)
        )

    async def _mutation(self, operation, request) -> None:
        try:
            await operation(request)
            if not await self.sync_with_coordinator():
                raise ServerError("Could not synchronize place mutation with coordinator")
        except grpc.aio.AioRpcError as exc:
            raise ServerError(exc.details()) from exc

    async def add_match(self, place: Place, match: ResourceMatch) -> bool:
        """Add a match; return False when an unnamed match already exists."""
        place = self.get_idle_place(place)
        pattern = repr(match)
        rename = match.rename or None
        if rename is not None:
            if "*" in pattern:
                raise InvalidResourceMatchError(f"invalid pattern '{pattern}' ('*' not allowed for named matches)")
        elif place.hasmatch(pattern.split("/")):
            return False
        await self._mutation(
            self.stub.AddPlaceMatch,
            labgrid_coordinator_pb2.AddPlaceMatchRequest(placename=place.name, pattern=pattern, rename=rename),
        )
        return True

    async def del_match(self, place: Place, match: ResourceMatch) -> None:
        """Remove a match from an idle place."""
        place = self.get_idle_place(place)
        await self._mutation(
            self.stub.DeletePlaceMatch,
            labgrid_coordinator_pb2.DeletePlaceMatchRequest(placename=place.name, pattern=repr(match)),
        )

    async def acquire_place(self, place: Place, allow_unmatched: bool = False) -> Place:
        """Acquire a place, marking it unavailable for other clients"""
        place = self.get_place(place)
        if place.acquired:
            host, user = place.acquired.split("/")
            if self.getuser() == user:
                if self.gethostname() == host:
                    raise PlaceAlreadyAcquiredError(f"You have already acquired place {place.name}.")
                else:
                    raise PlaceHostMismatchError(f"You have already acquired place {place.name} on {host}.", place)
            else:
                raise PlaceUserMismatchError(f"Place {place.name} is already acquired by {place.acquired}.", place)
        if not allow_unmatched:
            self.check_matches(place)

        request = labgrid_coordinator_pb2.AcquirePlaceRequest(placename=place.name)

        await self._mutation(self.stub.AcquirePlace, request)
        return place

    async def release_place(self, place: Place, kick: bool = False) -> Place:
        """Release a previously acquired place"""
        place = self.get_place(place)
        if not place.acquired:
            raise PlaceNotAcquiredError(f"place {place.name} is not acquired")
        _, user = place.acquired.split("/")
        if user != self.getuser() and not kick:
            raise PlaceReleasePermissionError(
                f"place {place.name} is acquired by a different user ({place.acquired})", place
            )

        request = labgrid_coordinator_pb2.ReleasePlaceRequest(placename=place.name)

        await self._mutation(self.stub.ReleasePlace, request)

        return place

    async def create_reservation(self, filters: Sequence[ReservationFilter], priority: float = 0.0) -> Reservation:
        """Create a reservation and return its domain representation."""
        values = {}
        for group in filters:
            tags = {}
            for tag in group.tags:
                pair = f"{tag.key}={tag.value}"
                if not TAG_KEY.match(tag.key):
                    raise InvalidReservationFilterError(f"Key '{tag.key}' in filter '{pair}' is invalid")
                if not TAG_VAL.match(tag.value):
                    raise InvalidReservationFilterError(f"Value '{tag.value}' in filter '{pair}' is invalid")
                tags[tag.key] = tag.value
            values[group.name] = labgrid_coordinator_pb2.Reservation.Filter(filter=tags)
        try:
            response = await self.stub.CreateReservation(
                labgrid_coordinator_pb2.CreateReservationRequest(filters=values, prio=priority)
            )
        except grpc.aio.AioRpcError as exc:
            raise ServerError(exc.details()) from exc
        return Reservation.from_pb2(response.reservation)

    async def cancel_reservation(self, reservation: Reservation | str) -> None:
        """Cancel a reservation identified by object or token."""
        token = reservation.token if isinstance(reservation, Reservation) else reservation
        try:
            await self.stub.CancelReservation(labgrid_coordinator_pb2.CancelReservationRequest(token=token))
        except grpc.aio.AioRpcError as exc:
            raise ServerError(exc.details()) from exc

    async def poll_reservation(self, reservation: Reservation | str) -> Reservation:
        """Refresh a reservation and return its current state."""
        token = reservation.token if isinstance(reservation, Reservation) else reservation
        try:
            response = await self.stub.PollReservation(labgrid_coordinator_pb2.PollReservationRequest(token=token))
        except grpc.aio.AioRpcError as exc:
            raise ServerError(exc.details()) from exc
        return Reservation.from_pb2(response.reservation)

    async def wait_reservation(self, reservation: Reservation | str) -> Reservation:
        """Poll until a reservation leaves the waiting state, then synchronize the place cache."""
        while True:
            current = await self.poll_reservation(reservation)
            if current.state is not ReservationState.waiting:
                if not await self.sync_with_coordinator():
                    raise ServerError("Could not synchronize reservation with coordinator")
                return current
            await asyncio.sleep(1.0)

    async def list_reservations(self) -> tuple[Reservation, ...]:
        """Fetch the coordinator's current reservations."""
        try:
            response = await self.stub.GetReservations(labgrid_coordinator_pb2.GetReservationsRequest())
        except grpc.aio.AioRpcError as exc:
            raise ServerError(exc.details()) from exc
        return tuple(Reservation.from_pb2(value) for value in response.reservations)

    def get_target_resources(self, place: Place) -> tuple[TargetResource, ...]:
        """Return named bindings to the acquired place's live resources."""
        self._check_allowed(place)
        resources = {}
        for resource_path in place.acquired_resources:
            match = place.getmatch(resource_path)
            (exporter, group_name, cls, resource_name) = resource_path
            name = resource_name
            if match.rename:
                name = match.rename
            try:
                resources[(name, cls)] = self.resources[exporter][group_name][resource_name]
            except KeyError:
                raise ServerError(f"place {place} has an orphaned resource (exporter {exporter} disconnected?)")

        return tuple(TargetResource(name, entry) for (name, _), entry in resources.items())

    def _prepare_manager(self):
        manager = RemotePlaceManager.get()
        manager.session = self
        manager.loop = self.loop

    def get_target(self, place: Place) -> Target:
        """Resolve the configured target or create a target for a remote place."""
        self._prepare_manager()
        target = None
        if self.env:
            selected_role = self.role
            if selected_role is None:
                for role, config in self.env.config.get_targets().items():
                    resources, _ = target_factory.normalize_config(config)
                    if resources.get("RemotePlace", {}).get(place.name):
                        selected_role = role
                        break
            target = self.env.get_target(selected_role)
        if target is None:
            target = Target(place.name, env=self.env)
            RemotePlace(target, name=place.name)
        return target


_loop: ContextVar[asyncio.AbstractEventLoop | None] = ContextVar("_loop", default=None)


def ensure_event_loop(external_loop: asyncio.AbstractEventLoop | None = None) -> asyncio.AbstractEventLoop:
    """Get the event loop for this thread, or create a new event loop."""
    # get stashed loop
    loop = _loop.get()

    # ignore closed stashed loop
    if loop and loop.is_closed():
        loop = None

    if external_loop:
        # if a loop is stashed, expect it to be the same as the external one
        if loop:
            assert loop is external_loop
        _loop.set(external_loop)
        return external_loop

    # return stashed loop
    if loop:
        return loop

    try:
        # if called from async code, try to get current's thread loop
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # no previous, external or running loop found, create a new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # stash it
    _loop.set(loop)
    return loop


def start_session(
    address: str,
    *,
    env: Environment | None = None,
    role: str | None = None,
    credentials: grpc.ChannelCredentials | None = None,
    debug: bool = False,
    loop: asyncio.AbstractEventLoop | None = None,
    username: str | None = None,
    hostname: str | None = None,
    token: str | None = None,
) -> ClientSession:
    """Start a session synchronously using explicit connection settings."""
    loop = ensure_event_loop(loop)
    if debug:
        loop.set_debug(True)
    address = proxymanager.get_grpc_address(address, default_port=20408)
    session = ClientSession(
        address, loop, credentials=credentials, env=env, role=role, username=username, hostname=hostname, token=token
    )
    try:
        loop.run_until_complete(session.start())
    except BaseException:
        loop.run_until_complete(session.stop())
        loop.run_until_complete(session.close())
        raise
    return session
