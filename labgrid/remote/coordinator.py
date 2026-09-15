#!/usr/bin/env python3
import argparse
import logging
import asyncio
import traceback
from enum import Enum
from functools import wraps
import time
from contextlib import contextmanager
import copy
import random
import signal
import pathlib
from typing import Optional
import os

import attr
import cel
import grpc
from grpc_health.v1 import health, health_pb2_grpc
from grpc_reflection.v1alpha import reflection

from labgrid.remote.identity import ClientIdentity, infer_peer_identity
from .auth.capability import Capability

from .common import (
    ResourceEntry,
    ResourceMatch,
    Place,
    Reservation,
    ReservationState,
    queue_as_aiter,
    TAG_KEY,
    TAG_VAL,
)
from .scheduler import TagSet, schedule
from .generated import labgrid_coordinator_pb2
from .generated import labgrid_coordinator_pb2_grpc
from .grpc.health import HealthServicer
from ..util import atomic_replace, labgrid_version, yaml, Timeout
from .otel import (
    record_reservation_wait_duration,
    setup_otel_metrics,
    setup_otel_sdk_if_available,
    set_traceparent_in_metadata,
)


@contextmanager
def warn_if_slow(prefix, *, level=logging.WARNING, limit=0.1):
    monotonic = time.monotonic()
    process = time.process_time()
    thread = time.thread_time()
    yield
    monotonic = time.monotonic() - monotonic
    process = time.process_time() - process
    thread = time.thread_time() - thread
    if monotonic > limit:
        logging.log(level, "%s: real %.3f>%.3f, process %.3f, thread %.3f", prefix, monotonic, limit, process, thread)


class Action(Enum):
    ADD = 0
    DEL = 1
    UPD = 2


@attr.s(init=False, eq=False)
class RemoteSession:
    """class encapsulating a session, used by ExporterSession and ClientSession"""

    coordinator = attr.ib()
    peer = attr.ib()
    name = attr.ib()
    queue = attr.ib()
    version = attr.ib()


@attr.s(eq=False)
class ExporterSession(RemoteSession):
    """An ExporterSession is opened for each Exporter connecting to the
    coordinator, allowing the Exporter to get and set resources"""

    groups = attr.ib(default=attr.Factory(dict), init=False)

    def set_resource(self, groupname, resourcename, resource):
        """This is called when Exporters update resources or when they disconnect."""
        logging.info("set_resource %s %s %s", groupname, resourcename, resource)
        group = self.groups.setdefault(groupname, {})
        old: ResourceImport = group.get(resourcename)
        if resource is not None:
            new = ResourceImport(
                data=ResourceImport.data_from_pb2(resource), path=(self.name, groupname, resource.cls, resourcename)
            )
            if old:
                old.data.update(new.data)
                new = old
            else:
                group[resourcename] = new
        else:
            new = None
            if old.acquired:
                old.orphaned = True
            try:
                del group[resourcename]
            except KeyError:
                pass

        msg = labgrid_coordinator_pb2.ClientOutMessage()
        update = msg.updates.add()
        if new:
            update.resource.CopyFrom(new.as_pb2())
            update.resource.path.exporter_name = self.name
            update.resource.path.group_name = groupname
            update.resource.path.resource_name = resourcename
        else:
            update.del_resource.exporter_name = self.name
            update.del_resource.group_name = groupname
            update.del_resource.resource_name = resourcename

        for client in self.coordinator.clients.values():
            client.queue.put_nowait(msg)

        if old and new:
            assert old is new
            return Action.UPD, new
        elif old and not new:
            return Action.DEL, old
        elif not old and new:
            return Action.ADD, new

        assert not old and not new

    def get_resources(self):
        """Method invoked by the client, get the resources from the coordinator"""
        result = {}
        for groupname, group in self.groups.items():
            result_group = result[groupname] = {}
            for resourcename, resource in group.items():
                result_group[resourcename] = resource.asdict()
        return result


@attr.s(eq=False)
class ClientSession(RemoteSession):
    def subscribe_places(self):
        # send initial places
        out_msg = labgrid_coordinator_pb2.ClientOutMessage()
        for place in self.coordinator.places.values():
            place: Place
            out_msg.updates.add().place.CopyFrom(place.as_pb2())
        self.queue.put_nowait(out_msg)

    def subscribe_resources(self):
        # collect initial resources
        collected = []
        logging.debug("sending resources to %s", self)
        for exporter in self.coordinator.exporters.values():
            logging.debug("sending resources %s", exporter)
            exporter: ExporterSession
            for groupname, group in exporter.groups.items():
                logging.debug("sending resources %s", groupname)
                for resourcename, resource in group.items():
                    logging.debug("sending resources %s", resourcename)
                    resource: ResourceImport
                    update = labgrid_coordinator_pb2.UpdateResponse()
                    update.resource.CopyFrom(resource.as_pb2())
                    update.resource.path.exporter_name = exporter.name
                    update.resource.path.group_name = groupname
                    update.resource.path.resource_name = resourcename
                    collected.append(update)
        # send batches
        while collected:
            batch, collected = collected[:100], collected[100:]
            out_msg = labgrid_coordinator_pb2.ClientOutMessage()
            out_msg.updates.extend(batch)
            self.queue.put_nowait(out_msg)


@attr.s(eq=False)
class ResourceImport(ResourceEntry):
    """Represents a local resource exported from an exporter.

    The ResourceEntry attributes contain the information for the client.
    """

    path = attr.ib(kw_only=True, validator=attr.validators.instance_of(tuple))
    orphaned = attr.ib(init=False, default=False, validator=attr.validators.instance_of(bool))


def locked(func):
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        async with self.lock:
            return await func(self, *args, **kwargs)

    return wrapper


async def check_capability(cls, identity, capability, context):
    if not cls.use_capabilities:
        return
    if not identity:
        await context.abort(grpc.StatusCode.UNAUTHENTICATED, "Client identity is required when using capabilities")
    if capability not in identity.capabilities:
        await context.abort(
            grpc.StatusCode.PERMISSION_DENIED,
            f"Capability {capability} not in client capabilities {identity.capabilities}",
        )


def require_capability(req_cap):
    def decorator(func):
        @wraps(func)
        async def wrapper(self, request, context):
            identity = ClientIdentity.from_metadata(context.invocation_metadata())
            await check_capability(self, identity, req_cap, context)
            return await func(self, request, context, identity=identity)

        return wrapper

    return decorator


def add_identity(func):
    @wraps(func)
    async def wrapper(self, request, context):
        identity = ClientIdentity.from_metadata(context.invocation_metadata())
        return await func(self, request, context, identity=identity)

    return wrapper


class ExporterCommand:
    def __init__(self, kind, request) -> None:
        self.kind = kind
        self.request = request
        self.response = None
        self.completed = asyncio.Event()
        self.expired = False

    def complete(self, response) -> None:
        self.response = response
        self.completed.set()
        if self.expired:
            logging.warning(
                "exporter command already expired for request %s -> response %s", self.request, self.response
            )

    async def wait(self):
        try:
            await asyncio.wait_for(self.completed.wait(), 10)
        finally:
            if self.response is None:
                self.expired = True


class CoordinatorError(Exception):
    pass


class ExporterError(CoordinatorError):
    pass


class LeaseExtendPreconditionError(CoordinatorError):
    pass


class Coordinator(labgrid_coordinator_pb2_grpc.CoordinatorServicer):
    def __init__(self, use_capabilities) -> None:
        self.use_capabilities = use_capabilities
        self.places: dict[str, Place] = {}
        self.reservations = {}
        self.poll_tasks = []
        self.save_scheduled = False

        self.lock = asyncio.Lock()
        self.exporters: dict[str, ExporterSession] = {}
        self.clients: dict[str, ClientSession] = {}
        self.default_lease_duration = int(
            os.environ.get("LG_DEFAULT_LEASE_DURATION", 15 * 60)
        )  # lease starts with 15 minutes
        self.default_extend_duration = int(
            os.environ.get("LG_DEFAULT_EXTEND_DURATION", 5 * 60)
        )  # every extend adds 5 minutes
        self.max_lease_duration = int(
            os.environ.get("LG_MAX_LEASE_DURATION", 2 * 60 * 60)
        )  # total from lease start can never exceed 2 hours
        self.poll_interval = float(os.environ.get("LG_COORDINATOR_POLL_INTERVAL", 15.0))

        if self.default_lease_duration <= 0:
            raise ValueError("LG_DEFAULT_LEASE_DURATION must be > 0")
        if self.default_extend_duration <= 0:
            raise ValueError("LG_DEFAULT_EXTEND_DURATION must be > 0")
        if self.max_lease_duration <= 0:
            raise ValueError("LG_MAX_LEASE_DURATION must be > 0")
        if self.default_lease_duration > self.max_lease_duration:
            raise ValueError("LG_DEFAULT_LEASE_DURATION must be <= LG_MAX_LEASE_DURATION")
        if self.default_extend_duration > self.max_lease_duration:
            raise ValueError("LG_DEFAULT_EXTEND_DURATION must be <= LG_MAX_LEASE_DURATION")
        if self.poll_interval <= 0:
            raise ValueError("LG_COORDINATOR_POLL_INTERVAL must be > 0")
        self.reservation_retry_cooldown = float(os.environ.get("LG_RESERVATION_RETRY_COOLDOWN", 60.0))
        self.reservation_place_cooldowns: dict[str, float] = {}

        if self.reservation_retry_cooldown <= 0:
            raise ValueError("LG_RESERVATION_RETRY_COOLDOWN must be > 0")
        self.load()

        self.loop = asyncio.get_running_loop()
        for name in ["save", "sync_resources", "schedule"]:
            step_func = getattr(self, f"_poll_step_{name}")
            task = self.loop.create_task(self.poll(step_func), name=f"coordinator-poll-{name}")
            self.poll_tasks.append(task)

    async def _poll_step_save(self):
        # save changes
        if self.save_scheduled:
            with warn_if_slow("save changes", level=logging.DEBUG):
                await self.save()

    async def _poll_step_sync_resources(self):
        # try to synchronize resources
        async with self.lock:
            with warn_if_slow("synchronize resources", limit=3.0):
                await self._synchronize_resources()

    async def _poll_step_schedule(self):
        # update reservations
        async with self.lock:
            with warn_if_slow("schedule reservations"):
                await self.schedule_reservations()

    async def poll(self, step_func):
        while not self.loop.is_closed():
            try:
                await asyncio.sleep(self.poll_interval)
                await step_func()
            except asyncio.CancelledError:
                break
            except Exception:  # pylint: disable=broad-except
                traceback.print_exc()

    def save_later(self):
        logging.debug("Setting Save-later")
        self.save_scheduled = True

    def _get_resources(self):
        result = {}
        for session in self.exporters.values():
            result[session.name] = session.get_resources()
        return result

    async def save(self):
        logging.debug("Running Save")
        self.save_scheduled = False

        with warn_if_slow("create resources snapshot", level=logging.DEBUG):
            resources = copy.deepcopy(self._get_resources())
        with warn_if_slow("create places snapshot", level=logging.DEBUG):
            places = copy.deepcopy(self._get_places())

        def save_sync(resources, places):
            with warn_if_slow("dump resources", level=logging.DEBUG):
                resources = yaml.dump(resources)
                resources = resources.encode()
            with warn_if_slow("dump places", level=logging.DEBUG):
                places = yaml.dump(places)
                places = places.encode()
            with warn_if_slow("write resources", level=logging.DEBUG):
                atomic_replace("resources.yaml", resources)
            with warn_if_slow("write places", level=logging.DEBUG):
                atomic_replace("places.yaml", places)

        await self.loop.run_in_executor(None, save_sync, resources, places)

    def load(self):
        try:
            self.places = {}
            with open("places.yaml", "r") as f:
                self.places = yaml.load(f.read())
            for placename, config in self.places.items():
                config["name"] = placename
                # FIXME maybe recover previously acquired places here?
                if "acquired" in config:
                    del config["acquired"]
                if "acquired_resources" in config:
                    del config["acquired_resources"]
                if "allowed" in config:
                    del config["allowed"]
                if "reservation" in config:
                    del config["reservation"]
                config["matches"] = [ResourceMatch(**match) for match in config["matches"]]
                place = Place(**config)
                self.places[placename] = place
        except FileNotFoundError:
            pass
        logging.info("loaded %s place(s)", len(self.places))

    async def ClientStream(self, request_iterator, context):
        peer = context.peer()
        logging.info("client connected: %s", peer)
        assert peer not in self.clients
        out_msg_queue = asyncio.Queue()

        identity = ClientIdentity.from_metadata(context.invocation_metadata())
        print(f"Stream identity: {identity}")
        if self.use_capabilities:
            await check_capability(self, identity, Capability.client_stream, context)

        if identity:
            logging.debug("client identity provided in gRPC metadata: %s", identity)
            self.clients[peer] = ClientSession(self, peer, identity.id, out_msg_queue, identity.user_agent)

        async def request_task():
            name = None
            version = None
            session = self.clients.get(peer)
            try:
                async for in_msg in request_iterator:
                    in_msg: labgrid_coordinator_pb2.ClientInMessage
                    logging.debug("client in_msg %s", in_msg)
                    kind = in_msg.WhichOneof("kind")
                    if kind == "sync":
                        out_msg = labgrid_coordinator_pb2.ClientOutMessage()
                        out_msg.sync.id = in_msg.sync.id
                        out_msg_queue.put_nowait(out_msg)
                    elif kind == "startup":
                        if session:
                            logging.debug("ignoring legacy startup message from client %s", peer)
                            name = session.name
                            version = identity.user_agent
                            continue
                        name = in_msg.startup.name
                        version = in_msg.startup.version
                        logging.warning(
                            "client %s did not provide identity metadata; using deprecated startup identity",
                            peer,
                        )
                        session = self.clients[peer] = ClientSession(self, peer, name, out_msg_queue, version)
                        logging.debug("Received startup from %s with %s", name, version)
                        asyncio.current_task().set_name(f"client-{peer}-rx/started-{name}")
                    elif kind == "subscribe":
                        if in_msg.subscribe.all_places:
                            session.subscribe_places()
                        if in_msg.subscribe.all_resources:
                            session.subscribe_resources()
                    else:
                        logging.warning("received unknown kind %s from client %s (version %s)", kind, name, version)
                logging.debug("client request_task done: %s", context.done())
            except Exception:
                logging.exception("error in client message handler")

        asyncio.current_task().set_name(f"client-{peer}-tx")
        running_request_task = self.loop.create_task(request_task(), name=f"client-{peer}-rx/init")

        try:
            async for out_msg in queue_as_aiter(out_msg_queue):
                out_msg: labgrid_coordinator_pb2.ClientOutMessage
                logging.debug("client output %s", out_msg)
                yield out_msg
        finally:
            try:
                session = self.clients.pop(peer)
                running_request_task.cancel()
                await running_request_task
                logging.debug("client aborted %s, cancelled: %s", session, context.cancelled())
            except KeyError:
                logging.info("Never received startup from peer %s that disconnected", peer)

    def _add_default_place(self, name):
        if name in self.places:
            return
        if not name.isdigit():
            return
        place = Place(name)
        print(place)
        place.matches.append(ResourceMatch(exporter="*", group=name, cls="*"))
        self.places[name] = place

    def get_exporter_by_name(self, name):
        for exporter in self.exporters.values():
            if exporter.name == name:
                return exporter

    async def _cleanup_exporter(self, peer, request_task):
        request_task.cancel()
        try:
            await request_task
        except asyncio.CancelledError:
            pass
        except Exception:
            logging.exception("error in exporter request task during cleanup")

        session = self.exporters.pop(peer, None)
        if session is None:
            logging.info("Never received startup from peer %s that disconnected", peer)
            return

        for groupname, group in session.groups.items():
            for resourcename in group.copy():
                session.set_resource(groupname, resourcename, None)

        logging.debug("exporter aborted %s", peer)

    def _publish_place(self, place):
        msg = labgrid_coordinator_pb2.ClientOutMessage()
        msg.updates.add().place.CopyFrom(place.as_pb2())

        for client in self.clients.values():
            client.queue.put_nowait(msg)

    def _publish_resource(self, resource: ResourceImport):
        msg = labgrid_coordinator_pb2.ClientOutMessage()
        update = msg.updates.add()
        update.resource.CopyFrom(resource.as_pb2())
        update.resource.path.exporter_name = resource.path[0]
        update.resource.path.group_name = resource.path[1]
        update.resource.path.resource_name = resource.path[3]

        for client in self.clients.values():
            client.queue.put_nowait(msg)

    async def ExporterStream(self, request_iterator, context):
        peer = context.peer()
        logging.info("exporter connected: %s", peer)
        assert peer not in self.exporters

        identity = ClientIdentity.from_metadata(context.invocation_metadata())
        if self.use_capabilities:
            await check_capability(self, identity, Capability.exporter_stream, context)

        command_queue = asyncio.Queue()
        pending_commands = []

        startup_done = asyncio.Event()

        out_msg = labgrid_coordinator_pb2.ExporterOutMessage()
        out_msg.hello.version = labgrid_version()
        yield out_msg

        identity = ClientIdentity.from_metadata(context.invocation_metadata())
        if identity:
            logging.debug("exporter identity provided in gRPC metadata: %s", identity)
            if existing := self.get_exporter_by_name(identity.id):
                await context.abort(
                    grpc.StatusCode.ALREADY_EXISTS,
                    f"startup failed: exporter with name '{identity.id}' is already connected from {existing.peer}",
                )
            self.exporters[peer] = ExporterSession(self, peer, identity.id, command_queue, identity.user_agent)
            startup_done.set()

        async def request_task():
            name = None
            version = None
            session = self.exporters.get(peer)
            try:
                async for in_msg in request_iterator:
                    in_msg: labgrid_coordinator_pb2.ExporterInMessage
                    logging.debug("exporter in_msg %s", in_msg)
                    kind = in_msg.WhichOneof("kind")
                    if kind == "response":
                        cmd = pending_commands.pop(0)
                        cmd.complete(in_msg.response)
                        logging.debug("Command %s is done", cmd)
                    elif kind == "startup":
                        if session:
                            logging.debug("ignoring legacy startup message from exporter %s", peer)
                            name = session.name
                            version = identity.user_agent
                            continue
                        name = in_msg.startup.name
                        version = in_msg.startup.version
                        logging.warning(
                            "exporter %s did not provide identity metadata; using deprecated startup identity",
                            peer,
                        )
                        if existing := self.get_exporter_by_name(name):
                            raise ExporterError(
                                f"exporter with name '{name}' is already connected from {existing.peer}"
                            )
                        session = self.exporters[peer] = ExporterSession(self, peer, name, command_queue, version)
                        logging.debug("Exporters: %s", self.exporters)
                        logging.debug("Received startup from %s with %s", name, version)
                        asyncio.current_task().set_name(f"exporter-{peer}-rx/started-{name}")
                        startup_done.set()
                    elif kind == "resource":
                        logging.debug("Received resource from %s with %s", name, in_msg.resource)
                        action, _ = session.set_resource(
                            in_msg.resource.path.group_name, in_msg.resource.path.resource_name, in_msg.resource
                        )
                        if action is Action.ADD:
                            async with self.lock:
                                self._add_default_place(in_msg.resource.path.group_name)
                        self.save_later()
                    else:
                        logging.warning("received unknown kind %s from exporter %s (version %s)", kind, name, version)

                logging.debug("exporter request_task done: %s", context.done())
            except Exception:
                logging.exception("error in exporter message handler")
                raise

        asyncio.current_task().set_name(f"exporter-{peer}-tx")
        running_request_task = self.loop.create_task(request_task(), name=f"exporter-{peer}-rx/init")

        try:
            startup_done_task = self.loop.create_task(startup_done.wait())
            done, _ = await asyncio.wait(
                {startup_done_task, running_request_task},
                timeout=3,
                return_when=asyncio.FIRST_COMPLETED,
            )
            # clean up event task
            startup_done.set()
            await startup_done_task
            if running_request_task in done:
                # we probably had an exception during startup
                try:
                    await running_request_task
                except ExporterError as e:
                    await context.abort(grpc.StatusCode.ALREADY_EXISTS, f"startup failed: {e}")
                    raise
            elif startup_done_task not in done:
                raise ExporterError(f"exporter connection from {peer} timed out during startup")

            async for cmd in queue_as_aiter(command_queue):
                logging.debug("exporter cmd %s", cmd)
                out_msg = labgrid_coordinator_pb2.ExporterOutMessage()
                set_traceparent_in_metadata(out_msg, cmd)
                if cmd.kind == "set_acquired_request":
                    out_msg.set_acquired_request.CopyFrom(cmd.request)
                elif cmd.kind == "lease_started_request":
                    out_msg.lease_started_request.CopyFrom(cmd.request)
                elif cmd.kind == "lease_extended_request":
                    out_msg.lease_extended_request.CopyFrom(cmd.request)
                else:
                    raise ValueError(f"unknown exporter command kind {cmd.kind}")
                pending_commands.append(cmd)
                yield out_msg
        except asyncio.exceptions.CancelledError:
            logging.info("exporter disconnected %s", context.peer())
        except Exception:
            logging.exception("error in exporter command handler")
            raise
        finally:
            await self._cleanup_exporter(peer, running_request_task)

    async def create_place(
        self,
        request: labgrid_coordinator_pb2.CreatePlaceRequest | labgrid_coordinator_pb2.AddPlaceRequest,
        context,
    ) -> Place:
        name = request.name
        if not name or not isinstance(name, str):
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "name was not a string")
        if name in self.places:
            await context.abort(grpc.StatusCode.ALREADY_EXISTS, f"Place {name} already exists")
        logging.debug("Adding %s", name)
        place = Place(name)
        self.places[name] = place
        self._publish_place(place)
        self.save_later()
        return place

    @require_capability(Capability.add_place)
    @locked
    async def AddPlace(self, request, context, *, identity):
        await self.create_place(request, context)
        return labgrid_coordinator_pb2.AddPlaceResponse()

    @require_capability(Capability.create_place)
    @locked
    async def CreatePlace(self, request, context, *, identity):
        logging.debug("CreatePlace name=%s", request.name)
        place = await self.create_place(request, context)
        return labgrid_coordinator_pb2.CreatePlaceResponse(place=place.as_pb2())

    @require_capability(Capability.delete_place)
    @locked
    async def DeletePlace(self, request, context, *, identity):
        name = request.name
        if not name or not isinstance(name, str):
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "name was not a string")
        if name not in self.places:
            await context.abort(grpc.StatusCode.ALREADY_EXISTS, f"Place {name} does not exist")
        logging.debug("Deleting %s", name)
        del self.places[name]
        msg = labgrid_coordinator_pb2.ClientOutMessage()
        msg.updates.add().del_place = name
        for client in self.clients.values():
            client.queue.put_nowait(msg)
        self.save_later()
        return labgrid_coordinator_pb2.DeletePlaceResponse()

    @require_capability(Capability.add_place_alias)
    @locked
    async def AddPlaceAlias(self, request, context, *, identity):
        placename = request.placename
        alias = request.alias
        try:
            place = self.places[placename]
        except KeyError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Place {placename} does not exist")
        place.aliases.add(alias)
        place.touch()
        self._publish_place(place)
        self.save_later()
        return labgrid_coordinator_pb2.AddPlaceAliasResponse()

    @require_capability(Capability.delete_place_alias)
    @locked
    async def DeletePlaceAlias(self, request, context, *, identity):
        placename = request.placename
        alias = request.alias
        try:
            place = self.places[placename]
        except KeyError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Place {placename} does not exist")
        try:
            place.aliases.remove(alias)
        except ValueError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Failed to remove {alias} from {placename}")
        place.touch()
        self._publish_place(place)
        self.save_later()
        return labgrid_coordinator_pb2.DeletePlaceAliasResponse()

    @require_capability(Capability.set_place_tags)
    @locked
    async def SetPlaceTags(self, request, context, *, identity):
        placename = request.placename
        tags = dict(request.tags)
        try:
            place = self.places[placename]
        except KeyError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Place {placename} does not exist")
        assert isinstance(tags, dict)
        for k, v in tags.items():
            assert isinstance(k, str)
            assert isinstance(v, str)
            if not TAG_KEY.match(k):
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Key {k} in {tags} is invalid")
            if not TAG_VAL.match(v):
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Value {v} in {tags} is invalid")
        for k, v in tags.items():
            if not v:
                try:
                    del place.tags[k]
                except KeyError:
                    pass
            else:
                place.tags[k] = v
        place.touch()
        self._publish_place(place)
        self.save_later()
        return labgrid_coordinator_pb2.SetPlaceTagsResponse()

    @require_capability(Capability.set_place_comment)
    @locked
    async def SetPlaceComment(self, request, context, *, identity):
        placename = request.placename
        comment = request.comment
        try:
            place = self.places[placename]
        except KeyError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Place {placename} does not exist")
        place.comment = comment
        place.touch()
        self._publish_place(place)
        self.save_later()
        return labgrid_coordinator_pb2.SetPlaceCommentResponse()

    @require_capability(Capability.add_place_match)
    @locked
    async def AddPlaceMatch(self, request, context, *, identity):
        placename = request.placename
        pattern = request.pattern
        rename = request.rename if request.HasField("rename") else None
        try:
            place = self.places[placename]
        except KeyError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Place {placename} does not exist")
        rm = ResourceMatch(*pattern.split("/"), rename=rename)
        if rm in place.matches:
            await context.abort(grpc.StatusCode.ALREADY_EXISTS, f"Match {rm} already exists")
        place.matches.append(rm)
        place.touch()
        self._publish_place(place)
        self.save_later()
        return labgrid_coordinator_pb2.AddPlaceMatchResponse()

    @require_capability(Capability.delete_place_match)
    @locked
    async def DeletePlaceMatch(self, request, context, *, identity):
        placename = request.placename
        pattern = request.pattern
        rename = request.rename if request.HasField("rename") else None
        try:
            place = self.places[placename]
        except KeyError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Place {placename} does not exist")
        rm = ResourceMatch(*pattern.split("/"), rename=rename)
        try:
            place.matches.remove(rm)
        except ValueError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Match {rm} does not exist in {placename}")
        place.touch()
        self._publish_place(place)
        self.save_later()
        return labgrid_coordinator_pb2.DeletePlaceMatchResponse()

    async def _acquire_resource(self, place, resource):
        assert self.lock.locked()

        # this triggers an update from the exporter which is published
        # to the clients
        request = labgrid_coordinator_pb2.ExporterSetAcquiredRequest()
        request.group_name = resource.path[1]
        request.resource_name = resource.path[3]
        request.place_name = place.name
        request.client_identity.id = place.acquired
        cmd = ExporterCommand("set_acquired_request", request)
        self.get_exporter_by_name(resource.path[0]).queue.put_nowait(cmd)
        try:
            await cmd.wait()
        except asyncio.TimeoutError as e:
            raise ExporterError("timed out waiting for exporter while acquiring resource") from e
        if not cmd.response.success:
            raise ExporterError(cmd.response.reason or "exporter returned failure without a reason")
        if resource.acquired != place.name:
            logging.warning("resource %s not acquired by this place after acquire request", resource)

    async def _lease_resource(self, place, resource, duration):
        assert self.lock.locked()

        # this triggers an update from the exporter which is published
        # to the clients
        request = labgrid_coordinator_pb2.ExporterLeaseStartedRequest()
        request.group_name = resource.path[1]
        request.resource_name = resource.path[3]
        request.place_name = place.name
        request.duration = duration
        request.client_identity.id = place.acquired
        cmd = ExporterCommand("lease_started_request", request)
        self.get_exporter_by_name(resource.path[0]).queue.put_nowait(cmd)
        try:
            await cmd.wait()
        except asyncio.TimeoutError as e:
            raise ExporterError("timed out waiting for exporter while leasing resource") from e
        if not cmd.response.success:
            raise ExporterError(cmd.response.reason or "exporter returned failure without a reason")
        if resource.acquired != place.name:
            logging.warning("resource %s not acquired by this place after lease request", resource)

    async def _acquire_resources(self, place, resources):
        assert self.lock.locked()

        resources = resources.copy()  # we may modify the list
        # all resources need to be free
        for resource in resources:
            if resource.acquired:
                raise CoordinatorError(
                    f"Resource {resource.path[0]}/{resource.path[1]}/{resource.path[3]} "
                    f"is already acquired by place '{resource.acquired}'"
                )

            for otherplace in self.places.values():
                for oldres in otherplace.acquired_resources:
                    if resource.path == oldres.path:
                        logging.info(
                            "Conflicting orphaned resource %s for acquire request for place %s", oldres, place.name
                        )
                        raise CoordinatorError(
                            f"conflicting orphaned resource {oldres} for acquire request for place {place.name}"
                        )

        # acquire resources
        acquired = []
        try:
            for resource in resources:
                await self._acquire_resource(place, resource)
                acquired.append(resource)
        except Exception as e:
            logging.exception("failed to acquire %s", resource)
            # cleanup
            try:
                await self._release_resources(place, acquired)
            except CoordinatorError:
                logging.exception("failed to release acquired resources during acquire cleanup")
            if isinstance(e, CoordinatorError):
                raise
            raise CoordinatorError(f"failed to acquire {resource}") from e

        for resource in resources:
            place.acquired_resources.append(resource)

    async def _lease_resources(self, place, resources, duration):
        assert self.lock.locked()

        resources = resources.copy()  # we may modify the list
        # all resources need to be free
        for resource in resources:
            if resource.acquired:
                raise CoordinatorError(f"{resource} is already acquired by {resource.acquired}")

            for otherplace in self.places.values():
                for oldres in otherplace.acquired_resources:
                    if resource.path == oldres.path:
                        logging.info(
                            "Conflicting orphaned resource %s for lease request for place %s", oldres, place.name
                        )
                        raise CoordinatorError(
                            f"conflicting orphaned resource {oldres} for lease request for place {place.name}"
                        )

        # lease resources
        leased = []
        try:
            for resource in resources:
                await self._lease_resource(place, resource, duration)
                leased.append(resource)
        except Exception as e:
            logging.exception("failed to lease %s", resource)
            # cleanup
            try:
                await self._release_resources(place, leased)
            except CoordinatorError:
                logging.exception("failed to release leased resources during lease cleanup")
            if isinstance(e, CoordinatorError):
                raise
            raise CoordinatorError(f"failed to lease {resource}") from e

        for resource in resources:
            place.acquired_resources.append(resource)

    async def _notify_lease_extended_resource(self, place, resource, duration):
        assert self.lock.locked()

        request = labgrid_coordinator_pb2.ExporterLeaseExtendedRequest()
        request.group_name = resource.path[1]
        request.resource_name = resource.path[3]
        if place is not None:
            request.place_name = place.name
        request.duration = duration

        cmd = ExporterCommand("lease_extended_request", request)
        self.get_exporter_by_name(resource.path[0]).queue.put_nowait(cmd)
        try:
            await cmd.wait()
        except asyncio.TimeoutError as e:
            raise ExporterError("timed out waiting for exporter while extending lease") from e

        if not cmd.response.success:
            raise ExporterError(f"failed to notify lease extension for {resource} ({cmd.response.reason})")

    async def _notify_lease_extended(self, place, duration):
        assert self.lock.locked()

        for resource in place.acquired_resources:
            if getattr(resource, "orphaned", False):
                raise LeaseExtendPreconditionError(
                    f"cannot extend lease for {place.name}: resource {resource} is orphaned"
                )

        for resource in place.acquired_resources:
            await self._notify_lease_extended_resource(place, resource, duration)

    async def _release_resources(self, place, resources, callback=True, acquirer_identity=None):
        assert self.lock.locked()

        # Empty identity means the release came from an internal cleanup path
        # where no client identity is available.
        acquirer_identity = acquirer_identity or ""
        resources = resources.copy()  # we may modify the list

        failure = None
        for resource in resources:
            if resource.orphaned or resource.acquired == "<broken>":
                try:
                    place.acquired_resources.remove(resource)
                except ValueError:
                    pass
                continue
            try:
                # this triggers an update from the exporter which is published
                # to the clients
                if callback:
                    exporter = self.get_exporter_by_name(resource.path[0])
                    if exporter is None:
                        try:
                            place.acquired_resources.remove(resource)
                        except ValueError:
                            pass
                        continue
                    request = labgrid_coordinator_pb2.ExporterSetAcquiredRequest()
                    request.group_name = resource.path[1]
                    request.resource_name = resource.path[3]
                    request.client_identity.id = acquirer_identity
                    # request.place_name is left unset to indicate release
                    cmd = ExporterCommand("set_acquired_request", request)
                    exporter.queue.put_nowait(cmd)
                    try:
                        await cmd.wait()
                    except asyncio.TimeoutError as e:
                        raise ExporterError("timed out waiting for exporter while releasing resource") from e
                    if not cmd.response.success:
                        raise ExporterError(cmd.response.reason or "exporter returned failure without a reason")
                    if resource.acquired:
                        logging.warning("resource %s still acquired after release request", resource)
                try:
                    place.acquired_resources.remove(resource)
                except ValueError:
                    pass
            except ExporterError as e:
                if failure is None:
                    failure = e
                logging.exception("failed to release %s", resource)
                # at leaset try to notify the clients
                try:
                    self._publish_resource(resource)
                except:
                    logging.exception("failed to publish released resource %s", resource)
        if failure is not None:
            raise failure

    async def _synchronize_resources(self):
        assert self.lock.locked()

        # fix:
        # - a resource is acquired for a place that is not acquired
        #   * perhaps caused by a resource acquire timeout (during normal lock)
        #   -> release()
        # - a resource is acquired for a place that still has it as orphaned
        #   * perhaps caused by a resource acquire timeout (during reacquire)
        #   -> replace orphaned resource
        # - a resource is released, but a place still has it as orphaned
        #   * perhaps caused by a exporter restart
        #   -> acquire() and replace orphaned resource

        acquired_resources = {}
        used_resources = {}
        orphaned_resources = {}

        # find acquired resources
        for exporter in self.exporters.values():
            for group in exporter.groups.values():
                for resource in group.values():
                    if resource.acquired:
                        acquired_resources[resource.path] = resource

        # find resources used by places
        for place in self.places.values():
            for resource in place.acquired_resources:
                if not resource.orphaned:
                    used_resources[resource.path] = resource
                else:
                    orphaned_resources[resource.path] = resource

        timeout = Timeout(5.0)

        # find resources to be released
        to_release = list(acquired_resources.keys() - used_resources.keys() - orphaned_resources.keys())
        if to_release:
            logging.info("synchronize resources: %s acquired resource(s) should be released", len(to_release))
            random.shuffle(to_release)  # don't get stuck on a problematic resource
        for resource_path in to_release:
            if timeout.expired:
                continue  # release the coordinator lock

            resource = acquired_resources[resource_path]
            if resource.acquired == "<broken>":
                continue
            place = self.places.get(resource.acquired)
            print(f"should release {resource} for {place}?")

            if place is None:
                logging.warning("resource %s claims to be acquired by unknown place", resource)
            elif not place.acquired:
                logging.warning("resource %s claims to be acquired by unacquired place", resource)
            else:
                continue
            try:
                await self._release_resources(place, [resource])
                del acquired_resources[resource_path]
            except Exception:
                logging.exception("failed to release unused resource %s", resource)
                break

        # find orphaned resources to be acquired
        to_acquire = list(orphaned_resources.keys() - acquired_resources.keys())
        if to_acquire:
            logging.info("synchronize resources: %s orphaned resource(s) should be acquired", len(to_acquire))
            random.shuffle(to_acquire)  # don't get stuck on a problematic resource
        for resource_path in to_acquire:
            if timeout.expired:
                continue  # release the coordinator lock

            resource = orphaned_resources[resource_path]
            if resource.acquired == "<broken>":
                continue
            place = self.places.get(resource.acquired)
            assert place is not None
            assert place.acquired
            print(f"should acquire {resource} for {place}?")

            # is the exporter connected again?
            exporter = self.get_exporter_by_name(resource.path[0])
            if not exporter:
                continue

            # does the resource exist again?
            try:
                new_resource = exporter.groups[resource.path[1]][resource.path[3]]
            except KeyError:
                continue

            if new_resource.acquired:
                # this should only happen when resources become broken
                logging.warning("ignoring acquired/broken resource %s for place %s", new_resource, place.name)
                continue

            try:
                await self._acquire_resource(place, new_resource)
                acquired_resources[new_resource.path] = new_resource
            except Exception:
                logging.exception("failed to reacquire orphaned resource %s for place %s", new_resource, place.name)
                break

        # find orphaned resources to be replaced in the places
        to_replace = set(orphaned_resources.keys() & acquired_resources.keys())
        if to_replace:
            logging.info("synchronize resources: %s orphaned resource(s) should be replaced", len(to_replace))
        for resource_path in set(orphaned_resources.keys() & acquired_resources.keys()):
            oldresource = orphaned_resources[resource_path]
            newresource = acquired_resources[resource_path]
            assert oldresource.acquired == newresource.acquired

            place = self.places.get(newresource.acquired)
            assert place is not None
            assert place.acquired

            idx = place.acquired_resources.index(oldresource)
            place.acquired_resources[idx] = newresource

    def _return_reservation_after_place_failure(self, place):
        assert self.lock.locked()

        reservation_id = place.reservation
        if not reservation_id:
            return

        reservation = self.reservations.get(reservation_id)
        if reservation is None:
            return

        reservation.state = ReservationState.waiting
        reservation.allocations.clear()
        reservation.lease_start_time = 0.0
        reservation.refresh()

        place.reservation = None
        place.acquired = None
        place.allowed = set()
        place.touch()
        self.reservation_place_cooldowns[place.name] = time.time() + self.reservation_retry_cooldown
        self._publish_place(place)
        self.save_later()

    async def _acquire_place_resources(self, place, owner):
        assert self.lock.locked()

        place.acquired = owner
        resources = []
        for _, session in sorted(self.exporters.items()):
            for _, group in sorted(session.groups.items()):
                for _, resource in sorted(group.items()):
                    if place.hasmatch(resource.path):
                        resources.append(resource)

        try:
            await self._acquire_resources(place, resources)
        except CoordinatorError:
            place.acquired = None
            raise

    async def _lease_place_resources(self, place, owner, duration):
        assert self.lock.locked()

        place.acquired = owner
        resources = []
        for _, session in sorted(self.exporters.items()):
            for _, group in sorted(session.groups.items()):
                for _, resource in sorted(group.items()):
                    if place.hasmatch(resource.path):
                        resources.append(resource)

        try:
            await self._lease_resources(place, resources, duration)
        except CoordinatorError:
            place.acquired = None
            raise

    @add_identity
    @locked
    async def AcquirePlace(self, request, context, *, identity):
        peer = context.peer()
        name = request.placename
        try:
            username = infer_peer_identity(self.clients, context, identity)
        except KeyError:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"Peer {peer} does not have a valid session")
        print(request)

        try:
            place = self.places[name]
        except KeyError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Place {name} does not exist")
        if place.acquired:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"Place {name} is already acquired")
        if place.reservation:
            res = self.reservations[place.reservation]
            if not res.owner == username:
                await context.abort(grpc.StatusCode.PERMISSION_DENIED, f"Place {name} was not reserved for {username}")

        # FIXME use the session object instead? or something else which
        # survives disconnecting clients?
        try:
            await self._acquire_place_resources(place, username)
        except CoordinatorError as e:
            reservation_returned = bool(place.reservation)
            if reservation_returned:
                self._return_reservation_after_place_failure(place)
                await self.schedule_reservations()
            message = f"Failed to acquire resources for place {name}"
            if str(e):
                message += f": {e}"
            if reservation_returned:
                message += "; reservation was returned to waiting state"
            await context.abort(
                grpc.StatusCode.FAILED_PRECONDITION,
                message,
            )
        if place.reservation:
            res = self.reservations[place.reservation]
            res.state = ReservationState.acquired
            res.refresh()
        place.touch()
        self._publish_place(place)
        self.save_later()
        await self.schedule_reservations()
        print(f"{place.name}: place acquired by {place.acquired}")
        return labgrid_coordinator_pb2.AcquirePlaceResponse()

    @add_identity
    @locked
    async def LeasePlace(self, request, context, *, identity):
        peer = context.peer()
        name = request.placename
        try:
            username = infer_peer_identity(self.clients, context, identity)
        except KeyError:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"Peer {peer} does not have a valid session")

        place = self.places.get(name)
        if place is None:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Place {name} does not exist")
        if place.acquired:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"Place {name} is already acquired")
        if not place.reservation:
            await context.abort(
                grpc.StatusCode.FAILED_PRECONDITION,
                f"Place {name} is not reserved; leasing requires a reservation",
            )

        res = self.reservations[place.reservation]
        if res.owner != username:
            await context.abort(
                grpc.StatusCode.PERMISSION_DENIED,
                f"Place {name} is reserved by a different user",
            )

        try:
            await self._lease_place_resources(place, username, self.default_lease_duration)
        except CoordinatorError as e:
            reservation_returned = bool(place.reservation)
            if reservation_returned:
                self._return_reservation_after_place_failure(place)
                await self.schedule_reservations()
            message = f"Failed to lease resources for place {name}"
            if str(e):
                message += f": {e}"
            if reservation_returned:
                message += "; reservation was returned to waiting state"
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, message)

        now = time.time()
        res.state = ReservationState.leased
        res.lease_start_time = now
        res.timeout = now + self.default_lease_duration

        place.touch()
        self._publish_place(place)
        self.save_later()
        await self.schedule_reservations()
        print(f"{place.name}: place leased by {place.acquired}")
        return labgrid_coordinator_pb2.LeasePlaceResponse()

    @add_identity
    @locked
    async def ReleasePlace(self, request, context, *, identity):

        if self.use_capabilities and not identity:
            await context.abort(grpc.StatusCode.UNAUTHENTICATED, "Client identity is required when using capabilities")

        name = request.placename
        fromuser = request.fromuser if request.HasField("fromuser") else None

        if fromuser and self.use_capabilities and not Capability.release_place_any in identity.capabilities:
            await context.abort(
                grpc.StatusCode.PERMISSION_DENIED,
                f"Capability {Capability.release_place_any} not in client capabilities {identity.capabilities}",
            )

        try:
            place = self.places[name]
        except KeyError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Place {name} does not exist")
        if not place.acquired:
            if fromuser:
                return labgrid_coordinator_pb2.ReleasePlaceResponse()
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"Place {name} is not acquired")
        if fromuser and place.acquired != fromuser:
            return labgrid_coordinator_pb2.ReleasePlaceResponse()

        try:
            acquirer_identity = infer_peer_identity(self.clients, context, identity)
        except KeyError:
            acquirer_identity = ""

        if self.use_capabilities:
            if not identity:
                await context.abort(
                    grpc.StatusCode.UNAUTHENTICATED, "Client identity is required when using capabilities"
                )

            owned = acquirer_identity == place.acquired
            if owned and not (
                Capability.release_place_owned in identity.capabilities
                or Capability.release_place_any in identity.capabilities
            ):
                await context.abort(
                    grpc.StatusCode.PERMISSION_DENIED,
                    f"Capability {Capability.release_place_owned} not in client capabilities {identity.capabilities}",
                )
            elif not owned and not Capability.release_place_any in identity.capabilities:
                await context.abort(
                    grpc.StatusCode.PERMISSION_DENIED,
                    f"Capability {Capability.release_place_any} not in client capabilities {identity.capabilities}",
                )

        try:
            await self._release_place(place, acquirer_identity=acquirer_identity)
        except CoordinatorError as e:
            place.touch()
            self._publish_place(place)
            self.save_later()
            message = f"Failed to release resources for place {name}"
            if str(e):
                message += f": {e}"
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, message)
        await self.schedule_reservations()
        return labgrid_coordinator_pb2.ReleasePlaceResponse()

    async def _release_place(self, place, acquirer_identity=None):
        assert self.lock.locked()
        await self._release_resources(place, place.acquired_resources, acquirer_identity=acquirer_identity)

        if place.reservation and place.reservation in self.reservations:
            reservation = self.reservations[place.reservation]
            if reservation.state is ReservationState.leased:
                reservation.state = ReservationState.expired
                reservation.allocations.clear()
                reservation.refresh()
                place.reservation = None
            elif reservation.state is ReservationState.acquired:
                reservation.state = ReservationState.allocated
                reservation.refresh()

        place.acquired = None
        place.allowed = set()
        place.touch()
        self._publish_place(place)
        self.save_later()
        print(f"{place.name}: place released")

    async def share_place(self, placename, user, context, *, identity):
        peer = context.peer()

        try:
            username = infer_peer_identity(self.clients, context, identity)
        except KeyError:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"Peer {peer} does not have a valid session")
        try:
            place = self.places[placename]
        except KeyError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Place {placename} does not exist")
        if not place.acquired:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"Place {placename} is not acquired")
        if place.acquired != username:
            await context.abort(
                grpc.StatusCode.FAILED_PRECONDITION, f"Place {placename} is not acquired by {username}"
            )

        place.allowed.add(user)
        place.touch()
        self._publish_place(place)
        self.save_later()

    @add_identity
    @locked
    async def AllowPlace(self, request, context, *, identity):
        placename = request.placename
        user = request.user
        peer = context.peer()

        try:
            username = infer_peer_identity(self.clients, context, identity)
        except KeyError:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"Peer {peer} does not have a valid session")
        try:
            place = self.places[placename]
        except KeyError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Place {placename} does not exist")
        if not place.acquired:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"Place {placename} is not acquired")
        owned = place.acquired == username
        if not owned and not self.use_capabilities:
            await context.abort(
                grpc.StatusCode.FAILED_PRECONDITION, f"Place {placename} is not acquired by {username}"
            )

        if self.use_capabilities:
            if not identity:
                await context.abort(
                    grpc.StatusCode.UNAUTHENTICATED, "Client identity is required when using capabilities"
                )
            if owned and not (
                Capability.allow_place_owned in identity.capabilities
                or Capability.allow_place_any in identity.capabilities
            ):
                await context.abort(
                    grpc.StatusCode.PERMISSION_DENIED,
                    f"Capability {Capability.allow_place_owned} not in client capabilities {identity.capabilities}",
                )
            elif not owned and not Capability.allow_place_any in identity.capabilities:
                await context.abort(
                    grpc.StatusCode.PERMISSION_DENIED,
                    f"Capability {Capability.allow_place_any} not in client capabilities {identity.capabilities}",
                )

        place.allowed.add(user)
        place.touch()
        self._publish_place(place)
        self.save_later()
        return labgrid_coordinator_pb2.AllowPlaceResponse()

    @add_identity
    @locked
    async def SharePlace(self, request, context, *, identity):
        name = request.name
        logging.debug("SharePlace name=%s user=%s", name, request.user)
        if not name or not isinstance(name, str):
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "name was not a string")

        await self.share_place(name, request.user, context, identity=identity)
        return labgrid_coordinator_pb2.SharePlaceResponse()

    @add_identity
    @locked
    async def UnsharePlace(self, request, context, *, identity):
        placename = request.name
        logging.debug("UnsharePlace name=%s user=%s", placename, request.user)
        if not placename or not isinstance(placename, str):
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "name was not a string")

        user = request.user
        peer = context.peer()
        try:
            username = infer_peer_identity(self.clients, context, identity)
        except KeyError:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"Peer {peer} does not have a valid session")
        try:
            place = self.places[placename]
        except KeyError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Place {placename} does not exist")
        if not place.acquired:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"Place {placename} is not acquired")
        if not place.acquired == username:
            await context.abort(
                grpc.StatusCode.FAILED_PRECONDITION, f"Place {placename} is not acquired by {username}"
            )
        try:
            place.allowed.remove(user)
            place.touch()
            self._publish_place(place)
            self.save_later()
        except KeyError:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"Place {placename} is not shared with {user}")

        return labgrid_coordinator_pb2.UnsharePlaceResponse()

    def _get_places(self):
        return {k: v.asdict() for k, v in self.places.items()}

    @require_capability(Capability.get_place)
    @locked
    async def GetPlace(self, request, context, *, identity):
        name = request.name
        logging.debug("GetPlace name=%s", name)
        if not name or not isinstance(name, str):
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "name was not a string")
        try:
            place = self.places[name]
            return labgrid_coordinator_pb2.GetPlaceResponse(place=place.as_pb2())
        except KeyError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Place {name} does not exist")
        except Exception:
            logging.exception("error during get place")
            await context.abort(grpc.StatusCode.INTERNAL, "internal error")

    @require_capability(Capability.get_places)
    @locked
    async def GetPlaces(self, unused_request, unused_context, *, identity):
        logging.debug("GetPlaces")
        try:
            return labgrid_coordinator_pb2.GetPlacesResponse(places=[x.as_pb2() for x in self.places.values()])
        except Exception:
            logging.exception("error during get places")

    @locked
    async def ListPlaces(self, request, context):
        logging.debug("ListPlaces")

        if request.page_size != 0 or request.page_token != "":
            await context.abort(grpc.StatusCode.UNIMPLEMENTED, "ListPlaces does not yet support pagination")

        filter_program = None
        if request.filter:
            try:
                filter_program = cel.compile(request.filter)  # pylint: disable=no-member
            except ValueError as exc:
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Invalid filter: {exc}")

        places = []
        for place in self.places.values():
            if filter_program is not None:
                filter_context = place.asdict()
                filter_context["name"] = place.name

                try:
                    filter_result = filter_program.execute(filter_context)
                    if not isinstance(filter_result, bool):
                        await context.abort(
                            grpc.StatusCode.INVALID_ARGUMENT,
                            "Filter must evaluate to a boolean",
                        )

                    if not filter_result:
                        continue
                except (RuntimeError, TypeError) as exc:
                    await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Invalid filter: {exc}")

            places.append(place.as_pb2())

        return labgrid_coordinator_pb2.ListPlacesResponse(places=places)

    @locked
    async def ListResources(self, request, context):
        logging.debug("ListResources")

        if request.page_size != 0 or request.page_token != "":
            await context.abort(grpc.StatusCode.UNIMPLEMENTED, "ListResources does not yet support pagination")

        filter_program = None
        if request.filter:
            try:
                filter_program = cel.compile(request.filter)  # pylint: disable=no-member
            except ValueError as exc:
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Invalid filter: {exc}")

        resources = []
        for _, session in sorted(self.exporters.items()):
            for _, group in sorted(session.groups.items()):
                for _, resource in sorted(group.items()):
                    if filter_program is not None:
                        filter_context = resource.asdict()
                        filter_context["path"] = {
                            "exporter_name": resource.path[0],
                            "group_name": resource.path[1],
                            "resource_name": resource.path[3],
                        }

                        try:
                            filter_result = filter_program.execute(filter_context)
                            if not isinstance(filter_result, bool):
                                await context.abort(
                                    grpc.StatusCode.INVALID_ARGUMENT,
                                    "Filter must evaluate to a boolean",
                                )

                            if not filter_result:
                                continue
                        except (RuntimeError, TypeError) as exc:
                            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Invalid filter: {exc}")

                    serialised = resource.as_pb2()
                    serialised.path.exporter_name = resource.path[0]
                    serialised.path.group_name = resource.path[1]
                    serialised.path.resource_name = resource.path[3]
                    resources.append(serialised)
        return labgrid_coordinator_pb2.ListResourcesResponse(resources=resources)

    @locked
    async def ListPlaceResources(self, request, context):
        name = request.name
        logging.debug("ListPlaceResources name=%s", name)
        if not name or not isinstance(name, str):
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "name was not a string")
        try:
            place = self.places[name]
        except KeyError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Place {name} does not exist")
        resources = []
        for _, session in sorted(self.exporters.items()):
            for _, group in sorted(session.groups.items()):
                for _, resource in sorted(group.items()):
                    if not place.hasmatch(resource.path):
                        continue
                    serialised = resource.as_pb2()
                    serialised.path.exporter_name = resource.path[0]
                    serialised.path.group_name = resource.path[1]
                    serialised.path.resource_name = resource.path[3]
                    resources.append(serialised)
        return labgrid_coordinator_pb2.ListPlaceResourcesResponse(resources=resources)

    async def schedule_reservations(self):
        # The primary information is stored in the reservations and the places
        # only have a copy for convenience.

        # expire reservations
        assert self.lock.locked()
        now = time.time()
        for name, cooldown_until in list(self.reservation_place_cooldowns.items()):
            if cooldown_until <= now:
                del self.reservation_place_cooldowns[name]
        for res in list(self.reservations.values()):
            if res.state is ReservationState.acquired:
                # acquired reservations do not expire
                res.refresh()

            if not res.expired:
                continue
            if res.state is ReservationState.leased:
                for place in list(self.places.values()):
                    if place.reservation == res.id and place.acquired == res.owner:
                        try:
                            await self._release_place(place)
                        except CoordinatorError:
                            logging.exception("failed to release expired lease on place %s; will retry", place.name)
                            place.touch()
                            self._publish_place(place)
                            self.save_later()
                        else:
                            print(f"marked leased reservation expired ({res.owner}/{res.id})")
                        break
                else:
                    res.state = ReservationState.expired
                    res.allocations.clear()
                    res.refresh()
                    print(f"marked leased reservation expired ({res.owner}/{res.id})")
                continue
            elif res.state is not ReservationState.expired:
                res.state = ReservationState.expired
                res.allocations.clear()
                res.refresh()
                print(f"reservation ({res.owner}/{res.id}) is now {res.state.name}")
            else:
                del self.reservations[res.id]
                print(f"removed {res.state.name} reservation ({res.owner}/{res.id})")

        # check which places are already allocated and handle state transitions
        allocated_places = set()
        for res in self.reservations.values():
            acquired_places = set()
            for group in list(res.allocations.values()):
                for name in group:
                    place = self.places.get(name)
                    if place is None:
                        # the allocated place was deleted
                        res.state = ReservationState.invalid
                        res.allocations.clear()
                        res.refresh(300)
                        print(f"reservation ({res.owner}/{res.id}) is now {res.state.name}")
                        break
                    elif res.state is ReservationState.leased and place.acquired != res.owner:
                        res.state = ReservationState.expired
                        res.allocations.clear()
                        res.refresh(300)
                        logging.info("marked leased reservation expired (%s/%s)", res.owner, res.id)
                        break
                    if place.acquired is not None:
                        acquired_places.add(name)
                    assert name not in allocated_places, "conflicting allocation"
                    allocated_places.add(name)
                else:
                    continue  # inner loop didn't break
                break  # inner loop broke -> break group loop
            # if the reservation was deleted, skip the rest
            if res.id not in self.reservations:
                continue

            if not acquired_places and res.state is ReservationState.acquired:
                # all allocated places were released
                res.state = ReservationState.allocated
                res.refresh()
                print(f"reservation ({res.owner}/{res.id}) is now {res.state.name}")

        # check which places are available for allocation
        available_places = set()
        for name, place in self.places.items():
            if name in self.reservation_place_cooldowns:
                continue
            if place.acquired is None and place.reservation is None:
                available_places.add(name)
        assert not (available_places & allocated_places), "inconsistent allocation"
        available_places -= allocated_places

        # check which reservations should be handled, ordered by priority and age
        pending_reservations = []
        for res in sorted(self.reservations.values(), key=lambda x: (-x.prio, x.created)):
            if res.state is not ReservationState.waiting:
                continue
            pending_reservations.append(res)

        # run scheduler
        place_tagsets = []
        for name in available_places:
            tags = set(self.places[name].tags.items())
            # support place names
            tags |= {("name", name)}
            # support place aliases
            place_tagsets.append(TagSet(name, tags))
        filter_tagsets = []
        for res in pending_reservations:
            filter_tagsets.append(TagSet(res.id, set(res.filters["main"].items())))
        allocation = schedule(place_tagsets, filter_tagsets)

        # apply allocations
        for res_id, place_name in allocation.items():
            res = self.reservations[res_id]
            res.allocations = {"main": [place_name]}
            res.state = ReservationState.allocated
            record_reservation_wait_duration(self, time.time() - res.created)
            res.refresh()
            print(f"reservation ({res.owner}/{res.id}) is now {res.state.name}")

        # update reservation property of each place and notify
        old_map = {}
        for place in self.places.values():
            old_map[place.name] = place.reservation
            place.reservation = None
        new_map = {}
        for res in self.reservations.values():
            if not res.allocations:
                continue
            assert len(res.allocations) == 1, "only one filter group is implemented"
            for group in res.allocations.values():
                for name in group:
                    assert name not in new_map, "conflicting allocation"
                    new_map[name] = res.id
                    place = self.places.get(name)
                    assert place is not None, "invalid allocation"
                    place.reservation = res.id
        for name in old_map.keys() | new_map.keys():
            if old_map.get(name) != new_map.get(name):
                self._publish_place(self.places[name])

    @require_capability(Capability.create_reservation)
    @locked
    async def CreateReservation(self, request: labgrid_coordinator_pb2.CreateReservationRequest, context, *, identity):
        peer = context.peer()

        fltrs = {}
        for name, fltr_pb in request.filters.items():
            if name != "main":
                await context.abort(
                    grpc.StatusCode.UNIMPLEMENTED, "Reservations for multiple groups are not implemented yet"
                )
            fltr = fltrs[name] = {}
            for k, v in fltr_pb.filter.items():
                if not TAG_KEY.match(k):
                    await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Key {k} is invalid")
                if not TAG_VAL.match(v):
                    await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Value {v} is invalid")
                fltr[k] = v

        try:
            owner = infer_peer_identity(self.clients, context, identity)
        except KeyError:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"Peer {peer} does not have a valid session")
        res = Reservation(owner=owner, prio=request.prio, filters=fltrs)
        self.reservations[res.id] = res
        await self.schedule_reservations()
        return labgrid_coordinator_pb2.CreateReservationResponse(reservation=res.as_pb2())

    @add_identity
    @locked
    async def CancelReservation(self, request: labgrid_coordinator_pb2.CancelReservationRequest, context, *, identity):
        reservation_id = request.token
        if not isinstance(reservation_id, str) or not reservation_id:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Invalid id {reservation_id}")
        if reservation_id not in self.reservations:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"Reservation {reservation_id} does not exist")

        reservation = self.reservations[reservation_id]
        try:
            owner = infer_peer_identity(self.clients, context, identity)
        except KeyError:
            await context.abort(
                grpc.StatusCode.FAILED_PRECONDITION, f"Peer {context.peer()} does not have a valid session"
            )

        owned = reservation.owner == owner
        if self.use_capabilities:
            if not identity:
                await context.abort(
                    grpc.StatusCode.UNAUTHENTICATED, "Client identity is required when using capabilities"
                )
            if owned and not (
                Capability.cancel_reservation_owned in identity.capabilities
                or Capability.cancel_reservation_any in identity.capabilities
            ):
                await context.abort(
                    grpc.StatusCode.PERMISSION_DENIED,
                    f"Capability {Capability.cancel_reservation_any} not in client capabilities {identity.capabilities}",
                )
            elif not owned and not Capability.cancel_reservation_any in identity.capabilities:
                await context.abort(
                    grpc.StatusCode.PERMISSION_DENIED,
                    f"Capability {Capability.cancel_reservation_any} not in client capabilities {identity.capabilities}",
                )

        # Cancelling a reservation for an active lease also releases the place.
        if reservation.state is ReservationState.leased:
            for place in list(self.places.values()):
                if place.reservation == reservation_id and place.acquired == reservation.owner:
                    await self._release_place(place)

        del self.reservations[reservation_id]
        await self.schedule_reservations()
        return labgrid_coordinator_pb2.CancelReservationResponse()

    async def refresh_reservation(self, reservation_id: str, context) -> Reservation:
        try:
            res = self.reservations[reservation_id]
        except KeyError:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"Reservation {reservation_id} does not exist")
        if res.state in (ReservationState.waiting, ReservationState.allocated):
            res.refresh()
        return res

    @require_capability(Capability.poll_reservation)
    @locked
    async def PollReservation(self, request: labgrid_coordinator_pb2.PollReservationRequest, context, *, identity):
        res = await self.refresh_reservation(request.token, context)
        return labgrid_coordinator_pb2.PollReservationResponse(reservation=res.as_pb2())

    @locked
    async def RefreshReservation(self, request: labgrid_coordinator_pb2.RefreshReservationRequest, context):
        logging.debug("RefreshReservation reservation_id=%s", request.reservation_id)
        res = await self.refresh_reservation(request.reservation_id, context)
        return labgrid_coordinator_pb2.RefreshReservationResponse(reservation=res.as_pb2())

    @require_capability(Capability.get_reservations)
    @locked
    async def GetReservations(self, request: labgrid_coordinator_pb2.GetReservationsRequest, context, *, identity):
        reservations = [x.as_pb2() for x in self.reservations.values()]
        return labgrid_coordinator_pb2.GetReservationsResponse(reservations=reservations)

    @locked
    async def ListReservations(self, request, context):
        if request.page_size != 0 or request.page_token != "":
            await context.abort(grpc.StatusCode.UNIMPLEMENTED, "ListReservations does not yet support pagination")

        filter_program = None
        if request.filter:
            try:
                filter_program = cel.compile(request.filter)  # pylint: disable=no-member
            except ValueError as exc:
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Invalid filter: {exc}")

        reservations = []
        for reservation in self.reservations.values():
            if filter_program is not None:
                filter_context = reservation.asdict()
                filter_context["token"] = reservation.id

                try:
                    filter_result = filter_program.execute(filter_context)
                    if not isinstance(filter_result, bool):
                        await context.abort(
                            grpc.StatusCode.INVALID_ARGUMENT,
                            "Filter must evaluate to a boolean",
                        )

                    if not filter_result:
                        continue
                except (RuntimeError, TypeError) as exc:
                    await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Invalid filter: {exc}")

            reservations.append(reservation.as_pb2())

        return labgrid_coordinator_pb2.ListReservationsResponse(reservations=reservations)

    async def GetLeaseConfig(self, request, context):
        return labgrid_coordinator_pb2.GetLeaseConfigResponse(
            default_lease_duration=self.default_lease_duration,
            default_extend_duration=self.default_extend_duration,
            max_lease_duration=self.max_lease_duration,
        )

    @add_identity
    @locked
    async def ExtendLease(self, request, context, *, identity):
        token = request.token

        if not isinstance(token, str) or not token:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Invalid token {token}")

        if token not in self.reservations:
            await context.abort(
                grpc.StatusCode.FAILED_PRECONDITION,
                f"Reservation {token} does not exist",
            )

        peer = context.peer()
        try:
            username = infer_peer_identity(self.clients, context, identity)
        except KeyError:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"Peer {peer} does not have a valid session")

        reservation = self.reservations[token]

        if reservation.owner != username:
            await context.abort(
                grpc.StatusCode.PERMISSION_DENIED,
                f"Reservation {token} is owned by a different user",
            )

        if reservation.expired:
            await context.abort(
                grpc.StatusCode.FAILED_PRECONDITION,
                f"Reservation {token} has expired",
            )

        if reservation.state is not ReservationState.leased:
            await context.abort(
                grpc.StatusCode.FAILED_PRECONDITION,
                f"Reservation {token} is not in leased state",
            )

        if reservation.lease_start_time <= 0:
            await context.abort(
                grpc.StatusCode.FAILED_PRECONDITION,
                f"Reservation {token} has invalid lease start time",
            )

        extend_duration = self.default_extend_duration
        requested_timeout = reservation.timeout + extend_duration
        max_timeout = reservation.lease_start_time + self.max_lease_duration
        remaining = max_timeout - reservation.timeout

        if requested_timeout > max_timeout:
            await context.abort(
                grpc.StatusCode.FAILED_PRECONDITION,
                f"Lease cannot be extended by {extend_duration} seconds; only {max(0, int(remaining))} seconds remain before reaching the maximum total lease duration of {self.max_lease_duration} seconds",
            )

        leased_place = None
        for place in self.places.values():
            if place.reservation == token and place.acquired == reservation.owner:
                leased_place = place
                break

        if leased_place is None:
            await context.abort(
                grpc.StatusCode.FAILED_PRECONDITION,
                f"Reservation {token} is leased but no acquired place was found",
            )

        try:
            await self._notify_lease_extended(leased_place, extend_duration)
        except LeaseExtendPreconditionError as e:
            await context.abort(
                grpc.StatusCode.FAILED_PRECONDITION,
                str(e),
            )
        except ExporterError as e:
            if len(leased_place.acquired_resources) == 1:
                await context.abort(
                    grpc.StatusCode.FAILED_PRECONDITION,
                    f"Lease extension failed and the lease was kept: {e}",
                )
            try:
                await self._release_place(leased_place)
                await self.schedule_reservations()
            except Exception:
                logging.exception("failed to clean up lease after extension failure")
            await context.abort(
                grpc.StatusCode.FAILED_PRECONDITION,
                f"Lease extension failed and the lease was cancelled: {e}",
            )
        reservation.timeout = requested_timeout
        self.save_later()

        return labgrid_coordinator_pb2.ExtendLeaseResponse(reservation=reservation.as_pb2())


async def serve(listen, cleanup, capabilities, server_credentials=None) -> None:
    asyncio.current_task().set_name("coordinator-serve")
    # It seems since https://github.com/grpc/grpc/pull/34647, the
    # ping_timeout_ms default of 60 seconds overrides keepalive_timeout_ms,
    # so set it as well.
    # Use GRPC_VERBOSITY=DEBUG GRPC_TRACE=http_keepalive for debugging.
    channel_options = [
        ("grpc.so_reuseport", 0),  # no load balancing
        ("grpc.keepalive_time_ms", 10000),  # 10 seconds
        ("grpc.keepalive_timeout_ms", 10000),  # 10 seconds
        ("grpc.http2.ping_timeout_ms", 15000),  # 15 seconds
        ("grpc.http2.min_ping_interval_without_data_ms", 5000),
        ("grpc.http2.max_pings_without_data", 0),  # no limit
        ("grpc.keepalive_permit_without_calls", 1),  # allow keepalive pings even when there are no calls
    ]
    server = grpc.aio.server(
        options=channel_options,
    )
    coordinator = Coordinator(capabilities)
    setup_otel_metrics(coordinator)
    labgrid_coordinator_pb2_grpc.add_CoordinatorServicer_to_server(coordinator, server)
    coordinator_service_name = labgrid_coordinator_pb2.DESCRIPTOR.services_by_name["Coordinator"].full_name
    # the empty name is explicitly maintained server liveness
    health_servicer = await HealthServicer.create(("", coordinator_service_name))
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)
    # enable reflection for use with grpcurl
    reflection.enable_server_reflection(
        (
            coordinator_service_name,
            health.SERVICE_NAME,
            reflection.SERVICE_NAME,
        ),
        server,
    )
    # optionally enable channelz for use with grpcdebug
    try:
        from grpc_channelz.v1 import channelz

        channelz.add_channelz_servicer(server)
        logging.info("Enabled channelz support")
    except ImportError:
        logging.info("Module grpcio-channelz not available")

    if server_credentials:
        bound = server.add_secure_port(listen, server_credentials)
    else:
        bound = server.add_insecure_port(listen)

    logging.debug("Starting server")
    await server.start()

    if inspect:
        inspect.coordinator = coordinator

    async def server_graceful_shutdown():
        logging.info("Starting graceful shutdown...")
        await health_servicer.enter_graceful_shutdown()
        # Shuts down the server with 0 seconds of grace period. During the
        # grace period, the server won't accept new connections and allow
        # existing RPCs to continue within the grace period.
        await server.stop(5)

    def callback():
        asyncio.ensure_future(server_graceful_shutdown())

    cleanup.append(server_graceful_shutdown())
    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, callback)
    loop.add_signal_handler(signal.SIGTERM, callback)
    # SERVING reports RPC availability, not exporter or device readiness.
    await health_servicer.mark_serving()
    logging.info("Coordinator ready")
    host, sep, port = listen.rpartition(":")
    if not sep or not port.isdigit():
        host = listen
    print(f"listening on {host}:{bound}", flush=True)
    await server.wait_for_termination()


def get_server_credentials(args: argparse.Namespace) -> Optional[grpc.ServerCredentials]:
    if not args.tls:
        return None

    if not args.cert or not args.key:
        raise RuntimeError("--cert and --key must be provided when --tls is provided")

    with open(args.key, "rb") as fk:
        with open(args.cert, "rb") as fc:
            return grpc.ssl_server_credentials([(fk.read(), fc.read())])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-l",
        "--listen",
        metavar="HOST:PORT",
        type=str,
        default="[::]:20408",
        help="coordinator listening host and port",
    )
    parser.add_argument("--tls", action="store_true", default=False, help="enable TLS gRPC channel")
    parser.add_argument("--cert", type=pathlib.PurePath, help="path to server TLS certificate (in PEM format)")
    parser.add_argument("--key", type=pathlib.PurePath, help="path to TLS key (in PEM format)")
    parser.add_argument("-d", "--debug", action="store_true", default=False, help="enable debug mode")
    parser.add_argument("--pystuck", action="store_true", help="enable pystuck")
    parser.add_argument(
        "--pystuck-port", metavar="PORT", type=int, default=6666, help="use a different pystuck port than 6666"
    )
    parser.add_argument(
        "--capabilities",
        action="store_true",
        default=False,
        help="enable using capabilities, which also enforces client identities",
    )

    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    setup_otel_sdk_if_available(Coordinator, ExporterCommand)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    global inspect
    if args.pystuck:
        from types import SimpleNamespace

        inspect = SimpleNamespace()
        inspect.loop = loop

        import pystuck

        pystuck.run_server(port=args.pystuck_port)
    else:
        inspect = None

    cleanup = []
    loop.set_debug(True)
    try:
        server_credentials = get_server_credentials(args)
        loop.run_until_complete(serve(args.listen, cleanup, args.capabilities, server_credentials))
    finally:
        if cleanup:
            loop.run_until_complete(*cleanup)


if __name__ == "__main__":
    main()
