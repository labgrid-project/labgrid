"""The remote.client module contains the functionality to connect to a
coordinator, acquire a place and interact with the connected resources"""

import argparse
import asyncio
import contextlib
from contextvars import ContextVar
import enum
import os
import pathlib
import subprocess
import traceback
import logging
import signal
import sys
import shlex
import shutil
import json
import itertools
from textwrap import indent
from socket import gethostname
from getpass import getuser
from collections import defaultdict, OrderedDict
from datetime import datetime
from pprint import pformat
from typing import Any, Dict

import attr
import grpc

from .common import (
    ResourceEntry,
    ResourceMatch,
    Place,
    Reservation,
    ReservationState,
    TAG_KEY,
    TAG_VAL,
    queue_as_aiter,
)
from .. import Environment, Target, target_factory
from ..exceptions import NoDriverFoundError, NoResourceFoundError, InvalidConfigError
from .generated import labgrid_coordinator_pb2, labgrid_coordinator_pb2_grpc
from ..resource.remote import RemotePlaceManager, RemotePlace
from ..util import diff_dict, flat_dict, dump, atomic_replace, labgrid_version, Timeout
from ..util.proxy import proxymanager
from ..util.helper import processwrapper
from ..driver import Mode, ExecutionError
from ..logging import basicConfig, StepLogger

# This is a workround for the gRPC issue
# https://github.com/grpc/grpc/issues/38679.
# Since Python 3.12, an empty exception message is printed from gRPC
# during shutdown, although nothing seems to go wrong. As this is
# confusing for users, suppress the message by adding an indirection.
sys.excepthook = lambda type, value, traceback: sys.__excepthook__(type, value, traceback)


class Error(Exception):
    pass


class UserError(Error):
    pass


class ServerError(Error):
    pass


class InteractiveCommandError(Error):
    pass


@attr.s(eq=False)
class ClientSession:
    """The ClientSession encapsulates all the actions a Client can invoke on
    the coordinator."""

    address = attr.ib(validator=attr.validators.instance_of(str))
    loop = attr.ib(validator=attr.validators.instance_of(asyncio.BaseEventLoop))
    env = attr.ib(default=None, validator=attr.validators.optional(attr.validators.instance_of(Environment)))
    role = attr.ib(default=None, validator=attr.validators.optional(attr.validators.instance_of(str)))
    prog = attr.ib(default=None, validator=attr.validators.optional(attr.validators.instance_of(str)))
    args = attr.ib(default=None, validator=attr.validators.optional(attr.validators.instance_of(argparse.Namespace)))
    monitor = attr.ib(default=False, validator=attr.validators.instance_of(bool))

    def gethostname(self):
        return os.environ.get("LG_HOSTNAME", gethostname())

    def getuser(self):
        return os.environ.get("LG_USERNAME", getuser())

    def __attrs_post_init__(self):
        """Actions which are executed if a connection is successfully opened."""
        self.stopping = asyncio.Event()

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

    async def start(self):
        """Starts receiving resource and place updates from the coordinator."""
        self.resources = {}
        self.places = {}

        self.pump_task = self.loop.create_task(self.message_pump())
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

    async def stop(self):
        """Stops stream for resource and place updates started with ClientSession.start()."""
        self.out_queue.put_nowait(None)  # let the sender side exit gracefully
        if self.stream_call:
            self.stream_call.cancel()
        try:
            await self.pump_task
        except asyncio.CancelledError:
            pass
        self.cancel_pending_syncs()

    async def close(self):
        """Closes the channel to the coordinator."""
        await self.channel.close()

    async def sync_with_coordinator(self):
        """Wait for coordinator to process all previous messages in stream."""
        identifier = next(self.sync_id)
        event = self.sync_events[identifier] = asyncio.Event()
        msg = labgrid_coordinator_pb2.ClientInMessage()
        msg.sync.id = identifier
        logging.debug("sending sync %s", identifier)
        self.out_queue.put_nowait(msg)
        await event.wait()
        if self.stopping.is_set():
            logging.debug("sync %s failed", identifier)
        else:
            logging.debug("received sync %s", identifier)
        return not self.stopping.is_set()

    def cancel_pending_syncs(self):
        """Cancel all pending ClientSession.sync_with_coordinator() calls."""
        assert self.stopping.is_set()  # only call when something has gone wrong
        while True:
            try:
                identifier, event = self.sync_events.popitem()
                logging.debug("cancelling %s %s", identifier, event)
                event.set()
            except KeyError:
                break

    async def message_pump(self):
        """Task for receiving resource and place updates."""
        got_message = False
        try:
            self.stream_call = call = self.stub.ClientStream(queue_as_aiter(self.out_queue))
            async for out_msg in call:
                out_msg: labgrid_coordinator_pb2.ClientOutMessage
                got_message = True
                logging.debug("out_msg from coordinator: %s", out_msg)
                for update in out_msg.updates:
                    update_kind = update.WhichOneof("kind")
                    if update_kind == "resource":
                        resource: labgrid_coordinator_pb2.Resource = update.resource
                        await self.on_resource_changed(
                            resource.path.exporter_name,
                            resource.path.group_name,
                            resource.path.resource_name,
                            ResourceEntry.data_from_pb2(resource),
                        )
                    elif update_kind == "del_resource":
                        resource_path: labgrid_coordinator_pb2.Resource.Path = update.del_resource
                        await self.on_resource_changed(
                            resource_path.exporter_name, resource_path.group_name, resource_path.resource_name, {}
                        )
                    elif update_kind == "place":
                        place = update.place
                        await self.on_place_changed(place)
                    elif update_kind == "del_place":
                        place_name = update.del_place
                        await self.on_place_deleted(place_name)
                    else:
                        logging.warning("unknown update from coordinator! %s", update_kind)
                if out_msg.HasField("sync"):
                    event = self.sync_events.pop(out_msg.sync.id)
                    event.set()
        except grpc.aio.AioRpcError as e:
            if e.code() == grpc.StatusCode.UNAVAILABLE:
                if got_message:
                    logging.error("coordinator became unavailable: %s", e.details())
                else:
                    logging.error("coordinator is unavailable: %s", e.details())
            else:
                logging.exception("unexpected grpc error in coordinator message pump task")
        except Exception:
            logging.exception("error in coordinator message pump task")
        finally:
            self.stopping.set()
            self.out_queue.put_nowait(None)  # let the sender side exit gracefully
            self.cancel_pending_syncs()

    async def on_resource_changed(self, exporter, group_name, resource_name, resource):
        group = self.resources.setdefault(exporter, {}).setdefault(group_name, {})
        # Do not replace the ResourceEntry object, as other components may keep
        # a reference to it and want to see changes.
        if resource_name not in group:
            old = None
            group[resource_name] = ResourceEntry(resource)
        else:
            old = group[resource_name].data
            group[resource_name].data = resource
        if self.monitor:
            if "cls" in resource and not old:
                print(f"Resource {exporter}/{group_name}/{resource['cls']}/{resource_name} created: {resource}")
            elif "cls" in resource and old:
                print(f"Resource {exporter}/{group_name}/{resource['cls']}/{resource_name} changed:")
                for k, v_old, v_new in diff_dict(flat_dict(old), flat_dict(resource)):
                    print(f"  {k}: {v_old} -> {v_new}")
            else:
                print(f"Resource {exporter}/{group_name}/???/{resource_name} deleted")

    async def on_place_changed(self, place_pb2: labgrid_coordinator_pb2.Place):
        name = place_pb2.name

        if name not in self.places:
            self.places[name] = Place.from_pb2(place_pb2)
            if self.monitor:
                print(f"Place {name} created: {place_pb2}")
        else:
            place = self.places[name]
            old = flat_dict(place.asdict())
            place.update_from_pb2(place_pb2)
            new = flat_dict(place.asdict())
            if self.monitor:
                print(f"Place {name} changed:")
                for k, v_old, v_new in diff_dict(old, new):
                    print(f"  {k}: {v_old} -> {v_new}")

    async def on_place_deleted(self, name: str):
        del self.places[name]
        if self.monitor:
            print(f"Place {name} deleted")

    async def do_monitor(self):
        self.monitor = True
        await self.stopping.wait()

    async def complete(self):
        if self.args.type == "resources":
            for exporter, groups in sorted(self.resources.items()):
                for group_name, group in sorted(groups.items()):
                    for _, resource in sorted(group.items()):
                        print(f"{exporter}/{group_name}/{resource.cls}")
        elif self.args.type == "places":
            for name in sorted(self.places.keys()):
                print(name)
        elif self.args.type == "matches":
            place = self.get_place()
            for match in place.matches:
                print(repr(match))
        elif self.args.type == "match-names":
            place = self.get_place()
            match_names = {match.rename for match in place.matches if match.rename is not None}
            print("\n".join(match_names))

    def _get_places_by_resource(self, resource_path):
        """Yield Place objects that match the given resource path"""
        for place in self.places.values():
            match = place.getmatch(resource_path)
            if match:
                yield place

    async def print_resources(self):
        """Print out the resources"""
        match = ResourceMatch.fromstr(self.args.match) if self.args.match else None

        # filter self.resources according to the arguments
        nested = lambda: defaultdict(nested)
        filtered = nested()
        for exporter, groups in sorted(self.resources.items()):
            if self.args.exporter and exporter != self.args.exporter:
                continue
            for group_name, group in sorted(groups.items()):
                for resource_name, resource in sorted(group.items()):
                    if not (resource.avail or self.args.verbose >= 2):
                        continue
                    if self.args.acquired and resource.acquired is None:
                        continue
                    if match and not match.ismatch((exporter, group_name, resource.cls, resource_name)):
                        continue

                    filtered[exporter][group_name][resource_name] = resource

        # print the filtered resources
        if self.args.verbose and not self.args.sort_by_matched_place_change:
            for exporter, groups in sorted(filtered.items()):
                print(f"Exporter '{exporter}':")
                for group_name, group in sorted(groups.items()):
                    print(f"  Group '{group_name}' ({exporter}/{group_name}/*):")
                    for resource_name, resource in sorted(group.items()):
                        print(
                            "    Resource '{res}' ({exporter}/{group}/{res_cls}[/{res}]):".format(
                                res=resource_name, exporter=exporter, group=group_name, res_cls=resource.cls
                            )
                        )
                        print(indent(pformat(resource.asdict()), prefix="      "))
        else:
            results = []
            for exporter, groups in sorted(filtered.items()):
                for group_name, group in sorted(groups.items()):
                    for resource_name, resource in sorted(group.items()):
                        if self.args.sort_by_matched_place_change:
                            resource_path = (exporter, group_name, resource.cls, resource_name)
                            places = list(self._get_places_by_resource(resource_path))
                            # most recently changed place last
                            places = sorted(places, key=lambda p: p.changed, reverse=True)
                        else:
                            places = None

                        results.append((places, exporter, group_name, resource.cls))

            results = sorted(results, key=lambda res: res[0][0].changed if res[0] else 0)

            for places, exporter, group_name, resource_cls in results:
                if self.args.sort_by_matched_place_change:
                    places_strs = [f"{p.name}: {datetime.fromtimestamp(p.changed):%Y-%m-%d}" for p in places]
                    places_info = ", ".join(places_strs) if places_strs else "not used by any place"

                else:
                    places_info = None

                line = f"{exporter}/{group_name}/{resource_cls}"
                if places_info is not None:
                    print(f"{line:<50s} {places_info}")
                else:
                    print(line)

    async def print_places(self):
        """Print out the places"""
        if self.args.sort_last_changed:
            places = sorted(self.places.items(), key=lambda p: p[1].changed)
        else:
            places = sorted(self.places.items())

        for name, place in places:
            if self.args.acquired and place.acquired is None:
                continue
            if self.args.released and place.acquired:
                continue
            if self.args.verbose:
                print(f"Place '{name}':")
                place.show(level=1)
            else:
                line = f"{name}"

                if place.aliases:
                    line += f" ({' '.join(place.aliases)})"

                print(f"{line:<40s} {place.comment}")

    def print_who(self):
        """Print acquired places by user"""
        result = ["User Host Place Changed".split()]
        if self.args.show_exporters:
            result[0].append("Exporters")

        for name, place in self.places.items():
            if place.acquired is None:
                continue
            host, user = place.acquired.split("/")
            result.append([user, host, name, str(datetime.fromtimestamp(place.changed))])
            if self.args.show_exporters:
                exporters = {resource_path[0] for resource_path in place.acquired_resources}
                result[-1].append(", ".join(sorted(exporters)))
        result.sort()

        widths = [max(map(len, c)) for c in zip(*result)]
        layout = []
        for i, w in enumerate(widths):
            layout.append("{%i:<%is}" % (i, w))
        layout = "  ".join(layout)

        for entry in result:
            print(layout.format(*entry))

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
                token = os.environ.get("LG_TOKEN", None)
            if not token:
                return []
            for name, place in self.places.items():
                if place.reservation == token:
                    result.add(name)
            if not result:
                raise UserError(f"reservation token {token} matches nothing")
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
            raise UserError(f"place {place.name} is not acquired")
        if f"{self.gethostname()}/{self.getuser()}" not in place.allowed:
            host, user = place.acquired.split("/")
            if user != self.getuser():
                raise UserError(
                    f"place {place.name} is not acquired by your user, acquired by {user}. To work simultaneously, {user} can execute labgrid-client -p {place.name} allow {self.gethostname()}/{self.getuser()}"
                )
            if host != self.gethostname():
                raise UserError(
                    f"place {place.name} is not acquired on this computer, acquired on {host}. To allow this host, use labgrid-client -p {place.name} allow {self.gethostname()}/{self.getuser()} on the other host"
                )

    def get_place(self, place=None):
        pattern = place or self.args.place
        if pattern is None:
            raise UserError("place pattern not specified")
        places = self._match_places(pattern)
        if not places:
            raise UserError(f"place pattern {pattern} matches nothing")
        if pattern in places:
            return self.places[pattern]
        if len(places) > 1:
            raise UserError(f"pattern {pattern} matches multiple places ({', '.join(places)})")
        return self.places[places[0]]

    def get_idle_place(self, place=None):
        place = self.get_place(place)
        if place.acquired:
            _, user = place.acquired.split("/")
            raise UserError(
                f"place {place.name} is not idle (acquired by {place.acquired}). To work simultaneously, {user} can execute labgrid-client -p {place.name} allow {self.gethostname()}/{self.getuser()}"
            )
        return place

    def get_acquired_place(self, place=None):
        place = self.get_place(place)
        self._check_allowed(place)
        return place

    async def print_place(self):
        """Print out the current place and related resources"""
        place = self.get_place()
        print(f"Place '{place.name}':")
        place.show(level=1)
        if place.acquired:
            for resource_path in place.acquired_resources:
                (exporter, group_name, cls, resource_name) = resource_path
                match = place.getmatch(resource_path)
                name = resource_name
                if match.rename:
                    name = match.rename
                try:
                    resource = self.resources[exporter][group_name][resource_name]
                except KeyError:
                    print(f"Orphaned resource '{name}' ({exporter}/{group_name}/{cls}/{resource_name})")
                    continue
                print(f"Acquired resource '{name}' ({exporter}/{group_name}/{resource.cls}/{resource_name}):")  # pylint: disable=line-too-long
                print(indent(pformat(resource.asdict()), prefix="  "))
                assert resource.cls == cls
        else:
            for exporter, groups in sorted(self.resources.items()):
                for group_name, group in sorted(groups.items()):
                    for resource_name, resource in sorted(group.items()):
                        resource_path = (exporter, group_name, resource.cls, resource_name)
                        match = place.getmatch(resource_path)
                        if match is None:
                            continue
                        name = resource_name
                        if match.rename:
                            name = match.rename
                        print(f"Matching resource '{name}' ({exporter}/{group_name}/{resource.cls}/{resource_name}):")  # pylint: disable=line-too-long
                        print(indent(pformat(resource.asdict()), prefix="  "))

    async def add_place(self):
        """Add a place to the coordinator"""
        name = self.args.place
        if not name:
            raise UserError("missing place name. Set with -p <place> or via env var LG_PLACE")

        request = labgrid_coordinator_pb2.AddPlaceRequest(name=name)
        try:
            await self.stub.AddPlace(request)
            await self.sync_with_coordinator()
        except grpc.aio.AioRpcError as e:
            raise ServerError(e.details())

    async def del_place(self):
        """Delete a place from the coordinator"""
        place = self.get_idle_place()
        request = labgrid_coordinator_pb2.DeletePlaceRequest(name=place.name)
        try:
            await self.stub.DeletePlace(request)
            await self.sync_with_coordinator()
        except grpc.aio.AioRpcError as e:
            raise ServerError(e.details())

    async def add_alias(self):
        """Add an alias for a place on the coordinator"""
        place = self.get_idle_place()
        alias = self.args.alias

        request = labgrid_coordinator_pb2.AddPlaceAliasRequest(placename=place.name, alias=alias)

        try:
            await self.stub.AddPlaceAlias(request)
            await self.sync_with_coordinator()
        except grpc.aio.AioRpcError as e:
            raise ServerError(e.details())

    async def del_alias(self):
        """Delete an alias for a place from the coordinator"""
        place = self.get_idle_place()
        alias = self.args.alias

        request = labgrid_coordinator_pb2.DeletePlaceAliasRequest(placename=place.name, alias=alias)

        try:
            await self.stub.DeletePlaceAlias(request)
            await self.sync_with_coordinator()
        except grpc.aio.AioRpcError as e:
            raise ServerError(e.details())

    async def set_comment(self):
        """Set the comment on a place"""
        place = self.get_place()
        comment = " ".join(self.args.comment)

        request = labgrid_coordinator_pb2.SetPlaceCommentRequest(placename=place.name, comment=comment)

        try:
            await self.stub.SetPlaceComment(request)
            await self.sync_with_coordinator()
        except grpc.aio.AioRpcError as e:
            raise ServerError(e.details())

    async def set_tags(self):
        """Set the tags on a place"""
        place = self.get_place()
        tags = {}
        for pair in self.args.tags:
            try:
                k, v = pair.split("=")
            except ValueError:
                raise UserError(f"tag '{pair}' needs to match '<key>=<value>'")
            if not TAG_KEY.match(k):
                raise UserError(f"tag key '{k}' needs to match the rexex '{TAG_KEY.pattern}'")
            if not TAG_VAL.match(v):
                raise UserError(f"tag value '{v}' needs to match the rexex '{TAG_VAL.pattern}'")
            tags[k] = v

        request = labgrid_coordinator_pb2.SetPlaceTagsRequest(placename=place.name, tags=tags)

        try:
            await self.stub.SetPlaceTags(request)
            await self.sync_with_coordinator()
        except grpc.aio.AioRpcError as e:
            raise ServerError(e.details())

    async def add_match(self):
        """Add a match for a place, making fuzzy matching available to the
        client"""
        place = self.get_idle_place()
        for pattern in self.args.patterns:
            if not 2 <= pattern.count("/") <= 3:
                raise UserError(f"invalid pattern format '{pattern}' (use 'exporter/group/cls/name')")
            if place.hasmatch(pattern.split("/")):
                print(f"pattern '{pattern}' exists, skipping", file=sys.stderr)
                continue

            request = labgrid_coordinator_pb2.AddPlaceMatchRequest(placename=place.name, pattern=pattern)

            try:
                await self.stub.AddPlaceMatch(request)
                await self.sync_with_coordinator()
            except grpc.aio.AioRpcError as e:
                raise ServerError(e.details())

    async def del_match(self):
        """Delete a match for a place"""
        place = self.get_idle_place()
        for pattern in self.args.patterns:
            if not 2 <= pattern.count("/") <= 3:
                raise UserError(f"invalid pattern format '{pattern}' (use 'exporter/group/cls/name')")
            if not place.hasmatch(pattern.split("/")):
                print(f"pattern '{pattern}' not found, skipping", file=sys.stderr)

            request = labgrid_coordinator_pb2.DeletePlaceMatchRequest(placename=place.name, pattern=pattern)

            try:
                await self.stub.DeletePlaceMatch(request)
                await self.sync_with_coordinator()
            except grpc.aio.AioRpcError as e:
                raise ServerError(e.details())

    async def add_named_match(self):
        """Add a named match for a place.

        Fuzzy matching is not allowed to avoid accidental names conflicts."""
        place = self.get_idle_place()
        pattern = self.args.pattern
        name = self.args.name
        if not 2 <= pattern.count("/") <= 3:
            raise UserError(f"invalid pattern format '{pattern}' (use 'exporter/group/cls/name')")
        if "*" in pattern:
            raise UserError(f"invalid pattern '{pattern}' ('*' not allowed for named matches)")

        request = labgrid_coordinator_pb2.AddPlaceMatchRequest(placename=place.name, pattern=pattern, rename=name)

        try:
            await self.stub.AddPlaceMatch(request)
            await self.sync_with_coordinator()
        except grpc.aio.AioRpcError as e:
            raise ServerError(e.details())

    def check_matches(self, place):
        resources = []
        for exporter, groups in self.resources.items():
            for group_name, group in groups.items():
                for resource_name, resource in group.items():
                    resource_path = (exporter, group_name, resource.cls, resource_name)
                    resources.append(resource_path)

        match = place.unmatched(resources)
        if match:
            raise UserError(f"Match {match} has no matching remote resource")

    async def acquire(self):
        """Acquire a place, marking it unavailable for other clients"""
        place = self.get_idle_place()
        if not self.args.allow_unmatched:
            self.check_matches(place)

        request = labgrid_coordinator_pb2.AcquirePlaceRequest(placename=place.name)

        try:
            await self.stub.AcquirePlace(request)
            await self.sync_with_coordinator()
            print(f"acquired place {place.name}")
        except grpc.aio.AioRpcError as e:
            # check potential failure causes
            for exporter, groups in sorted(self.resources.items()):
                for group_name, group in sorted(groups.items()):
                    for resource_name, resource in sorted(group.items()):
                        resource_path = (exporter, group_name, resource.cls, resource_name)
                        if not resource.acquired:
                            continue
                        match = place.getmatch(resource_path)
                        if match is None:
                            continue
                        name = resource_name
                        if match.rename:
                            name = match.rename
                        print(
                            f"Matching resource '{name}' ({exporter}/{group_name}/{resource.cls}/{resource_name}) already acquired by place '{resource.acquired}'"
                        )  # pylint: disable=line-too-long

            raise ServerError(e.details())

    async def release(self):
        """Release a previously acquired place"""
        place = self.get_place()
        if not place.acquired:
            raise UserError(f"place {place.name} is not acquired")
        _, user = place.acquired.split("/")
        if user != self.getuser():
            if not self.args.kick:
                raise UserError(
                    f"place {place.name} is acquired by a different user ({place.acquired}), use --kick if you are sure"
                )  # pylint: disable=line-too-long
            print(f"warning: kicking user ({place.acquired})")

        request = labgrid_coordinator_pb2.ReleasePlaceRequest(placename=place.name)

        try:
            await self.stub.ReleasePlace(request)
            await self.sync_with_coordinator()
        except grpc.aio.AioRpcError as e:
            raise ServerError(e.details())

        print(f"released place {place.name}")

    async def release_from(self):
        """Release a place, but only if acquired by a specific user"""
        place = self.get_place()
        if not place.acquired:
            raise UserError(f"place {place.name} is not acquired")

        request = labgrid_coordinator_pb2.ReleasePlaceRequest(placename=place.name, fromuser=self.args.acquired)

        try:
            await self.stub.ReleasePlace(request)
            await self.sync_with_coordinator()
        except grpc.aio.AioRpcError as e:
            raise ServerError(e.details())

        print(f"{self.args.acquired} has released place {place.name}")

    async def allow(self):
        """Allow another use access to a previously acquired place"""
        place = self.get_acquired_place()
        if "/" not in self.args.user:
            raise UserError(f"user {self.args.user} must be in <host>/<username> format")
        request = labgrid_coordinator_pb2.AllowPlaceRequest(placename=place.name, user=self.args.user)

        try:
            await self.stub.AllowPlace(request)
            await self.sync_with_coordinator()
        except grpc.aio.AioRpcError as e:
            raise ServerError(e.details())

        print(f"allowed {self.args.user} for place {place.name}")

    def get_target_resources(self, place):
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

        return resources

    def get_target_config(self, place):
        config = {}
        resources = config["resources"] = []
        for (name, _), resource in self.get_target_resources(place).items():
            args = OrderedDict()
            if name != resource.cls:
                args["name"] = name
            args.update(resource.args)
            resources.append({resource.cls: args})
        return config

    def print_env(self):
        place = self.get_acquired_place()
        env = {"targets": {place.name: self.get_target_config(place)}}
        print(dump(env))

    def _prepare_manager(self):
        manager = RemotePlaceManager.get()
        manager.session = self
        manager.loop = self.loop

    def _get_target(self, place):
        self._prepare_manager()
        target = None
        if self.env:
            if self.role is None:
                self.role = find_role_by_place(self.env.config.get_targets(), place.name)
                if self.role is not None:
                    print(f"Selected role {self.role} from configuration file")
            target = self.env.get_target(self.role)
        if target:
            if self.args.state:
                strategy = target.get_driver("Strategy")
                if self.args.initial_state:
                    print(f"Setting initial state to {self.args.initial_state}")
                    strategy.force(self.args.initial_state)
                print(f"Transitioning into state {self.args.state}")
                strategy.transition(self.args.state)
                # deactivate console drivers so we are able to connect with microcom later
                try:
                    con = target.get_active_driver("ConsoleProtocol")
                    target.deactivate(con)
                except NoDriverFoundError:
                    pass
        else:
            target = Target(place.name, env=self.env)
            RemotePlace(target, name=place.name)
        return target

    def _get_driver_or_new(self, target, cls, *, name=None, activate=True):
        """
        Helper function trying to get an active driver. If no such driver
        exists, instanciates a new driver.
        Driver instanciation works only for drivers without special kwargs.

        Arguments:
        target -- target to operate on
        cls -- driver-class to retrieve active or instanciate new driver from
        name -- optional name to use as a filter
        activate -- activate the driver (default True)
        """
        try:
            return target.get_driver(cls, name=name, activate=activate)
        except NoDriverFoundError:
            if isinstance(cls, str):
                cls = target_factory.class_from_string(cls)

            if name is not None:
                # set name in binding map for unique bindings
                try:
                    [unique_binding_key] = cls.bindings
                    target.set_binding_map({unique_binding_key: name})
                except ValueError:
                    raise NotImplementedError("Multiple bindings not implemented for named resources")

            drv = cls(target, name=name)
            if activate:
                target.activate(drv)
            return drv

    def power(self):
        place = self.get_acquired_place()
        action = self.args.action
        delay = self.args.delay
        name = self.args.name
        target = self._get_target(place)
        from ..resource.power import NetworkPowerPort, PDUDaemonPort
        from ..resource.remote import NetworkUSBPowerPort, NetworkSiSPMPowerPort, NetworkSysfsGPIO
        from ..resource import TasmotaPowerPort, NetworkYKUSHPowerPort

        drv = None
        try:
            drv = target.get_driver("PowerProtocol", name=name)
        except NoDriverFoundError:
            for resource in target.resources:
                if name and resource.name != name:
                    continue
                if isinstance(resource, NetworkPowerPort):
                    drv = self._get_driver_or_new(target, "NetworkPowerDriver", name=name)
                elif isinstance(resource, NetworkUSBPowerPort):
                    drv = self._get_driver_or_new(target, "USBPowerDriver", name=name)
                elif isinstance(resource, NetworkSiSPMPowerPort):
                    drv = self._get_driver_or_new(target, "SiSPMPowerDriver", name=name)
                elif isinstance(resource, PDUDaemonPort):
                    drv = self._get_driver_or_new(target, "PDUDaemonDriver", name=name)
                elif isinstance(resource, TasmotaPowerPort):
                    drv = self._get_driver_or_new(target, "TasmotaPowerDriver", name=name)
                elif isinstance(resource, NetworkYKUSHPowerPort):
                    drv = self._get_driver_or_new(target, "YKUSHPowerDriver", name=name)
                elif isinstance(resource, NetworkSysfsGPIO):
                    self._get_driver_or_new(target, "GpioDigitalOutputDriver", name=name)
                    drv = self._get_driver_or_new(target, "DigitalOutputPowerDriver", name=name)
                if drv:
                    break

        if not drv:
            raise UserError("target has no compatible resource available")
        if delay is not None:
            drv.delay = delay
        res = getattr(drv, action)()
        if action == "get":
            print(f"power{' ' + name if name else ''} for place {place.name} is {'on' if res else 'off'}")

    def digital_io(self):
        place = self.get_acquired_place()
        action = self.args.action
        name = self.args.name
        target = self._get_target(place)
        from ..resource import ModbusTCPCoil, OneWirePIO, HttpDigitalOutput
        from ..resource.remote import NetworkDeditecRelais8, NetworkSysfsGPIO, NetworkLXAIOBusPIO, NetworkHIDRelay

        drv = None
        try:
            drv = target.get_driver("DigitalOutputProtocol", name=name)
        except NoDriverFoundError:
            for resource in target.resources:
                if isinstance(resource, ModbusTCPCoil):
                    drv = self._get_driver_or_new(target, "ModbusCoilDriver", name=name)
                elif isinstance(resource, OneWirePIO):
                    drv = self._get_driver_or_new(target, "OneWirePIODriver", name=name)
                elif isinstance(resource, HttpDigitalOutput):
                    drv = self._get_driver_or_new(target, "HttpDigitalOutputDriver", name=name)
                elif isinstance(resource, NetworkDeditecRelais8):
                    drv = self._get_driver_or_new(target, "DeditecRelaisDriver", name=name)
                elif isinstance(resource, NetworkSysfsGPIO):
                    drv = self._get_driver_or_new(target, "GpioDigitalOutputDriver", name=name)
                elif isinstance(resource, NetworkLXAIOBusPIO):
                    drv = self._get_driver_or_new(target, "LXAIOBusPIODriver", name=name)
                elif isinstance(resource, NetworkHIDRelay):
                    drv = self._get_driver_or_new(target, "HIDRelayDriver", name=name)
                if drv:
                    break

        if not drv:
            raise UserError("target has no compatible resource available")
        if action == "get":
            print(f"digital IO{' ' + name if name else ''} for place {place.name} is {'high' if drv.get() else 'low'}")
        elif action == "high":
            drv.set(True)
        elif action == "low":
            drv.set(False)

    async def _console(self, place, target, timeout, *, logfile=None, loop=False, listen_only=False):
        name = self.args.name
        from ..resource import NetworkSerialPort

        resource = target.get_resource(NetworkSerialPort, name=name, wait_avail=False)

        # async await resources
        timeout = Timeout(timeout)
        while True:
            target.update_resources()
            if resource.avail or (not loop and timeout.expired):
                break
            await asyncio.sleep(0.1)

        # use zero timeout to prevent blocking sleeps
        target.await_resources([resource], timeout=0.0)

        if not place.acquired:
            print("place released")
            return 255

        host, port = proxymanager.get_host_and_port(resource)

        # check for valid resources
        assert port is not None, "Port is not set"

        microcom_bin = shutil.which("microcom")

        if microcom_bin is not None:
            call = [microcom_bin, "-s", str(resource.speed), "-t", f"{host}:{port}"]

            if listen_only:
                call.append("--listenonly")

            if logfile:
                call.append(f"--logfile={logfile}")
        else:
            call = ["telnet", host, str(port)]

            logging.info("microcom not available, using telnet instead")

            if listen_only:
                logging.warning("--listenonly option not supported by telnet, ignoring")

            if logfile:
                logging.warning("--logfile option not supported by telnet, ignoring")

        print(f"connecting to {resource} calling {' '.join(call)}")
        try:
            p = await asyncio.create_subprocess_exec(*call)
        except FileNotFoundError as e:
            raise ServerError(f"failed to execute remote console command: {e}")
        while p.returncode is None:
            try:
                await asyncio.wait_for(p.wait(), 1.0)
            except asyncio.TimeoutError:
                # subprocess is still running
                pass

            try:
                self._check_allowed(place)
            except UserError:
                p.terminate()
                try:
                    await asyncio.wait_for(p.wait(), 1.0)
                except asyncio.TimeoutError:
                    # try harder
                    p.kill()
                    await asyncio.wait_for(p.wait(), 1.0)
                raise
        if p.returncode:
            print("connection lost", file=sys.stderr)
        return p.returncode

    async def console(self, place, target):
        while True:
            res = await self._console(
                place, target, 10.0, logfile=self.args.logfile, loop=self.args.loop, listen_only=self.args.listenonly
            )
            # place released
            if res == 255:
                break
            if not self.args.loop:
                if res:
                    exc = InteractiveCommandError("microcom error")
                    exc.exitcode = res
                    raise exc
                break
            await asyncio.sleep(1.0)

    console.needs_target = True

    def dfu(self):
        place = self.get_acquired_place()
        target = self._get_target(place)
        name = self.args.name
        if self.args.action == "download" and not self.args.filename:
            raise UserError("not enough arguments for dfu download")
        drv = self._get_driver_or_new(target, "DFUDriver", activate=False, name=name)
        drv.dfu.timeout = self.args.wait
        target.activate(drv)

        if self.args.action == "download":
            drv.download(self.args.altsetting, os.path.abspath(self.args.filename))
        if self.args.action == "detach":
            drv.detach(self.args.altsetting)
        if self.args.action == "list":
            drv.list()

    def fastboot(self):
        place = self.get_acquired_place()
        args = self.args.fastboot_args
        target = self._get_target(place)
        name = self.args.name

        drv = self._get_driver_or_new(target, "AndroidFastbootDriver", activate=False, name=name)
        drv.fastboot.timeout = self.args.wait
        target.activate(drv)

        try:
            action = args[0]
            if action == "flash":
                drv.flash(args[1], os.path.abspath(args[2]))
            elif action == "boot":
                args[1:] = map(os.path.abspath, args[1:])
                drv.boot(args[1])
            elif action == "oem" and args[1] == "exec":
                drv.run(" ".join(args[2:]))
            else:
                drv(*args)
        except IndexError:
            raise UserError("not enough arguments for fastboot action")
        except subprocess.CalledProcessError as e:
            raise UserError(str(e))

    def flashscript(self):
        place = self.get_acquired_place()
        target = self._get_target(place)
        name = self.args.name

        drv = self._get_driver_or_new(target, "FlashScriptDriver", name=name)
        drv.flash(script=self.args.script, args=self.args.script_args)

    def bootstrap(self):
        place = self.get_acquired_place()
        target = self._get_target(place)
        name = self.args.name
        from ..resource.remote import (
            NetworkMXSUSBLoader,
            NetworkIMXUSBLoader,
            NetworkRKUSBLoader,
            NetworkAlteraUSBBlaster,
        )
        from ..driver import OpenOCDDriver

        drv = None
        try:
            drv = target.get_driver("BootstrapProtocol", name=name)
        except NoDriverFoundError:
            for resource in target.resources:
                if isinstance(resource, NetworkIMXUSBLoader):
                    drv = self._get_driver_or_new(target, "IMXUSBDriver", activate=False, name=name)
                    drv.loader.timeout = self.args.wait
                elif isinstance(resource, NetworkMXSUSBLoader):
                    drv = self._get_driver_or_new(target, "MXSUSBDriver", activate=False, name=name)
                    drv.loader.timeout = self.args.wait
                elif isinstance(resource, NetworkAlteraUSBBlaster):
                    args = dict(arg.split("=", 1) for arg in self.args.bootstrap_args)
                    try:
                        drv = target.get_driver("OpenOCDDriver", activate=False, name=name)
                    except NoDriverFoundError:
                        drv = OpenOCDDriver(target, name=name, **args)
                    drv.interface.timeout = self.args.wait
                elif isinstance(resource, NetworkRKUSBLoader):
                    drv = self._get_driver_or_new(target, "RKUSBDriver", activate=False, name=name)
                    drv.loader.timeout = self.args.wait
                if drv:
                    break

        if not drv:
            raise UserError("target has no compatible resource available")
        target.activate(drv)
        drv.load(self.args.filename)

    def sd_mux(self):
        place = self.get_acquired_place()
        action = self.args.action
        target = self._get_target(place)
        name = self.args.name
        from ..resource.remote import NetworkUSBSDMuxDevice, NetworkUSBSDWireDevice

        drv = None
        for resource in target.resources:
            if isinstance(resource, NetworkUSBSDMuxDevice):
                drv = self._get_driver_or_new(target, "USBSDMuxDriver", name=name)
            elif isinstance(resource, NetworkUSBSDWireDevice):
                drv = self._get_driver_or_new(target, "USBSDWireDriver", name=name)
            if drv:
                break

        if not drv:
            raise UserError("target has no compatible resource available")
        if action == "get":
            print(drv.get_mode())
        else:
            try:
                drv.set_mode(action)
            except ExecutionError as e:
                raise UserError(str(e))

    def usb_mux(self):
        place = self.get_acquired_place()
        name = self.args.name
        links = self.args.links
        if links == "off":
            links = []
        elif links == "host-dut+host-device":
            links = ["host-dut", "host-device"]
        else:
            links = [links]
        target = self._get_target(place)
        from ..resource.remote import NetworkLXAUSBMux

        drv = None
        for resource in target.resources:
            if isinstance(resource, NetworkLXAUSBMux):
                drv = self._get_driver_or_new(target, "LXAUSBMuxDriver", name=name)
                break

        if not drv:
            raise UserError("target has no compatible resource available")
        drv.set_links(links)

    def _get_ip(self, place):
        target = self._get_target(place)
        try:
            resource = target.get_resource("EthernetPort")
        except NoResourceFoundError:
            resource = target.get_resource("NetworkService")
            return resource.address

        matches = []
        for details in resource.extra.get("macs").values():
            ips = details.get("ips", [])
            if not ips:
                continue
            matches.append((details["timestamp"], ips))
        matches.sort()
        newest = matches[-1][1]
        if len(ips) > 1:
            print(f"multiple IPs found: {ips}", file=sys.stderr)
            return None
        return newest[0]

    def _get_ssh(self):
        place = self.get_acquired_place()
        target = self._get_target(place)

        try:
            drv = target.get_driver("SSHDriver", name=self.args.name)
            return drv
        except NoDriverFoundError:
            from ..resource import NetworkService

            try:
                resource = target.get_resource(NetworkService, name=self.args.name)
            except NoResourceFoundError:
                ip = self._get_ip(place)
                if not ip:
                    return
                resource = NetworkService(target, address=str(ip), username="root")

            drv = self._get_driver_or_new(target, "SSHDriver", name=resource.name)
            return drv

    def ssh(self):
        drv = self._get_ssh()

        res = drv.interact(self.args.leftover)
        if res:
            exc = InteractiveCommandError("ssh error")
            exc.exitcode = res
            raise exc

    def scp(self):
        drv = self._get_ssh()

        res = drv.scp(src=self.args.src, dst=self.args.dst)
        if res:
            exc = InteractiveCommandError("scp error")
            exc.exitcode = res
            raise exc

    def rsync(self):
        drv = self._get_ssh()

        res = drv.rsync(src=self.args.src, dst=self.args.dst, extra=self.args.leftover)
        if res:
            exc = InteractiveCommandError("rsync error")
            exc.exitcode = res
            raise exc

    def sshfs(self):
        drv = self._get_ssh()

        drv.sshfs(path=self.args.path, mountpoint=self.args.mountpoint)

    def forward(self):
        if not self.args.local and not self.args.remote:
            print("Nothing to forward", file=sys.stderr)
            return

        drv = self._get_ssh()

        with contextlib.ExitStack() as stack:
            for local, remote in self.args.local:
                localport = stack.enter_context(drv.forward_local_port(remote, localport=local))
                print(f"Forwarding local port {localport:d} to remote port {remote:d}")

            for local, remote in self.args.remote:
                stack.enter_context(drv.forward_remote_port(remote, local))
                print(f"Forwarding remote port {remote:d} to local port {local:d}")

            try:
                print("Waiting for CTRL+C...")
                while True:
                    signal.pause()
            except KeyboardInterrupt:
                print("Exiting...")

    def telnet(self):
        place = self.get_acquired_place()
        ip = self._get_ip(place)
        if not ip:
            return
        args = ["telnet", str(ip)]
        res = subprocess.call(args)
        if res:
            exc = InteractiveCommandError("telnet error")
            exc.exitcode = res
            raise exc

    def video(self):
        place = self.get_acquired_place()
        quality = self.args.quality
        controls = self.args.controls
        target = self._get_target(place)
        name = self.args.name
        from ..resource.httpvideostream import HTTPVideoStream
        from ..resource.udev import USBVideo
        from ..resource.remote import NetworkUSBVideo

        drv = None
        try:
            drv = target.get_driver("VideoProtocol", name=name)
        except NoDriverFoundError:
            for resource in target.resources:
                if isinstance(resource, (USBVideo, NetworkUSBVideo)):
                    drv = self._get_driver_or_new(target, "USBVideoDriver", name=name)
                elif isinstance(resource, HTTPVideoStream):
                    drv = self._get_driver_or_new(target, "HTTPVideoDriver", name=name)
                if drv:
                    break
        if not drv:
            raise UserError("target has no compatible resource available")

        if quality == "list":
            default, variants = drv.get_qualities()
            for name, caps in variants:
                mark = "*" if default == name else " "
                print(f"{mark} {name:<10s} {caps:s}")
        else:
            res = drv.stream(quality, controls=controls)
            if res:
                exc = InteractiveCommandError("gst-launch-1.0 error")
                exc.exitcode = res
                raise exc

    def audio(self):
        place = self.get_acquired_place()
        target = self._get_target(place)
        name = self.args.name
        drv = self._get_driver_or_new(target, "USBAudioInputDriver", name=name)
        res = drv.play()
        if res:
            exc = InteractiveCommandError("gst-launch-1.0 error")
            exc.exitcode = res
            raise exc

    def _get_tmc(self):
        place = self.get_acquired_place()
        target = self._get_target(place)
        name = self.args.name

        return self._get_driver_or_new(target, "USBTMCDriver", name=name)

    def tmc_command(self):
        drv = self._get_tmc()
        command = " ".join(self.args.command)
        if not command:
            raise UserError("no command given")
        if "?" in command:
            result = drv.query(command)
            print(result)
        else:
            drv.command(command)

    def tmc_query(self):
        drv = self._get_tmc()
        query = " ".join(self.args.query)
        if not query:
            raise UserError("no query given")
        result = drv.query(query)
        print(result)

    def tmc_screen(self):
        drv = self._get_tmc()
        action = self.args.action
        if action in ["show", "save"]:
            extension, data = drv.get_screenshot()
            filename = "tmc-screen_{0:%Y-%m-%d}_{0:%H:%M:%S}.{1}".format(datetime.now(), extension)
            with open(filename, "wb") as f:
                f.write(data)
            print(f"Saved as {filename}")
            if action == "show":
                subprocess.call(["xdg-open", filename])

    def tmc_channel(self):
        drv = self._get_tmc()
        channel = self.args.channel
        action = self.args.action
        if action == "info":
            data = drv.get_channel_info(channel)
        elif action == "values":
            data = drv.get_channel_values(channel)
        else:
            raise ValueError(f"unknown action {action}")

        for k, v in sorted(data.items()):
            print(f"{k:<16s} {str(v):<10s}")

    def write_files(self):
        place = self.get_acquired_place()
        target = self._get_target(place)
        name = self.args.name
        drv = self._get_driver_or_new(target, "USBStorageDriver", activate=False, name=name)
        drv.storage.timeout = self.args.wait
        target.activate(drv)

        try:
            if self.args.partition == 0:
                self.args.partition = None

            if self.args.rename:
                if len(self.args.SOURCE) != 2:
                    self.args.parser.error("the following arguments are required: SOURCE DEST")

                drv.write_files(
                    [self.args.SOURCE[0]], self.args.SOURCE[1], self.args.partition, target_is_directory=False
                )
            else:
                drv.write_files(
                    self.args.SOURCE, self.args.target_directory, self.args.partition, target_is_directory=True
                )
        except subprocess.CalledProcessError as e:
            raise UserError(f"could not copy files to network usb storage: {e}")
        except FileNotFoundError as e:
            raise UserError(e)

    def write_image(self):
        place = self.get_acquired_place()
        target = self._get_target(place)
        name = self.args.name
        drv = self._get_driver_or_new(target, "USBStorageDriver", activate=False, name=name)
        drv.storage.timeout = self.args.wait
        target.activate(drv)

        try:
            drv.write_image(
                self.args.filename,
                partition=self.args.partition,
                skip=self.args.skip,
                seek=self.args.seek,
                mode=self.args.write_mode,
            )
        except subprocess.CalledProcessError as e:
            raise UserError(f"could not write image to network usb storage: {e}")
        except FileNotFoundError as e:
            raise UserError(e)

    async def create_reservation(self):
        prio = self.args.prio

        fltr = {}
        for pair in self.args.filters:
            try:
                k, v = pair.split("=")
            except ValueError:
                raise UserError(f"'{pair}' is not a valid filter (must contain a '=')")
            if not TAG_KEY.match(k):
                raise UserError(f"Key '{k}' in filter '{pair}' is invalid")
            if not TAG_VAL.match(v):
                raise UserError(f"Value '{v}' in filter '{pair}' is invalid")
            fltr[k] = v

        fltrs = {
            "main": labgrid_coordinator_pb2.Reservation.Filter(filter=fltr),
        }

        request = labgrid_coordinator_pb2.CreateReservationRequest(filters=fltrs, prio=prio)

        try:
            response: labgrid_coordinator_pb2.CreateReservationResponse = await self.stub.CreateReservation(request)
        except grpc.aio.AioRpcError as e:
            raise ServerError(e.details())

        res = Reservation.from_pb2(response.reservation)
        if self.args.shell:
            print(f"export LG_TOKEN={res.token}")
        else:
            print(f"Reservation '{res.token}':")
            res.show(level=1)
        if self.args.wait:
            if not self.args.shell:
                print("Waiting for allocation...")
            await self._wait_reservation(res.token, verbose=False)

    async def cancel_reservation(self):
        token: str = self.args.token

        request = labgrid_coordinator_pb2.CancelReservationRequest(token=token)

        try:
            await self.stub.CancelReservation(request)
        except grpc.aio.AioRpcError as e:
            raise ServerError(e.details())

    async def _wait_reservation(self, token: str, verbose=True):
        while True:
            request = labgrid_coordinator_pb2.PollReservationRequest(token=token)

            try:
                response: labgrid_coordinator_pb2.PollReservationResponse = await self.stub.PollReservation(request)
            except grpc.aio.AioRpcError as e:
                raise ServerError(e.details())

            res = Reservation.from_pb2(response.reservation)
            if verbose:
                res.show()
            if res.state is ReservationState.waiting:
                await asyncio.sleep(1.0)
            else:
                break

    async def wait_reservation(self):
        token = self.args.token
        await self._wait_reservation(token)

    async def print_reservations(self):
        request = labgrid_coordinator_pb2.GetReservationsRequest()

        try:
            response: labgrid_coordinator_pb2.GetReservationsResponse = await self.stub.GetReservations(request)
            reservations = [Reservation.from_pb2(x) for x in response.reservations]
        except grpc.aio.AioRpcError as e:
            raise ServerError(e.details())

        for res in sorted(reservations, key=lambda x: (-x.prio, x.created)):
            print(f"Reservation '{res.token}':")
            res.show(level=1)

    async def export(self, place, target):
        exported = target.export()
        exported["LG__CLIENT_PID"] = str(os.getpid())
        if self.args.format is ExportFormat.SHELL:
            lines = []
            for k, v in sorted(exported.items()):
                lines.append(f"{k}={shlex.quote(v)}")
            data = "\n".join(lines)
        elif self.args.format is ExportFormat.SHELL_EXPORT:
            lines = []
            for k, v in sorted(exported.items()):
                lines.append(f"export {k}={shlex.quote(v)}")
            data = "\n".join(lines) + "\n"
        elif self.args.format is ExportFormat.JSON:
            data = json.dumps(exported)
        else:
            raise NotImplementedError(f"unsupported format {self.args.format}")

        if self.args.filename == "-":
            sys.stdout.write(data)
        else:
            atomic_replace(self.args.filename, data.encode())
            print(f"Exported to {self.args.filename}", file=sys.stderr)
        try:
            print("Waiting for CTRL+C or SIGTERM...", file=sys.stderr)
            while True:
                await asyncio.sleep(1.0)
        except GeneratorExit:
            print("Exiting...\n", file=sys.stderr)

    export.needs_target = True

    def print_version(self):
        print(labgrid_version())


_loop: ContextVar["asyncio.AbstractEventLoop | None"] = ContextVar("_loop", default=None)


def ensure_event_loop(external_loop=None):
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
    address: str, *, extra: Dict[str, Any] = None, debug: bool = False, loop: "asyncio.AbstractEventLoop | None" = None
):
    """
    Starts a ClientSession.

    Args:
        address: coordinator address as HOST[:PORT], PORT defaults to 20408
        extra: additional kwargs for ClientSession
        debug: set debug mode of the event loop
        loop: explicit event loop to use (otherwise a previously stashed loop,
              if retrievable the current thread's loop or a new loop is used)
    """
    loop = ensure_event_loop(loop)

    if extra is None:
        extra = {}

    if debug:
        loop.set_debug(True)

    address = proxymanager.get_grpc_address(address, default_port=20408)

    session = ClientSession(address, loop, **extra)
    loop.run_until_complete(session.start())
    return session


def find_role_by_place(config, place):
    for role, role_config in config.items():
        resources, _ = target_factory.normalize_config(role_config)
        remote_places = resources.get("RemotePlace", {})
        remote_place = remote_places.get(place)
        if remote_place:
            return role
    return None


def find_any_role_with_place(config):
    for role, role_config in config.items():
        resources, _ = target_factory.normalize_config(role_config)
        remote_places = resources.get("RemotePlace", {})
        for place in remote_places:
            return (role, place)
    return None, None


class LocalPort(argparse.Action):
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        if nargs is not None:
            raise ValueError("nargs not allowed")
        super().__init__(option_strings, dest, nargs=None, default=[], **kwargs)

    def __call__(self, parser, namespace, value, option_string):
        if ":" in value:
            (local, remote) = value.split(":")
            local = int(local)
            remote = int(remote)
        else:
            local = None
            remote = int(value)

        v = getattr(namespace, self.dest, [])
        v.append((local, remote))
        setattr(namespace, self.dest, v)


class RemotePort(argparse.Action):
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        if nargs is not None:
            raise ValueError("nargs not allowed")
        super().__init__(option_strings, dest, nargs=None, default=[], **kwargs)

    def __call__(self, parser, namespace, value, option_string):
        (remote, local) = value.split(":")
        remote = int(remote)
        local = int(local)

        v = getattr(namespace, self.dest, [])
        v.append((local, remote))
        setattr(namespace, self.dest, v)


class ExportFormat(enum.Enum):
    SHELL = "shell"
    SHELL_EXPORT = "shell-export"
    JSON = "json"

    def __str__(self):
        return self.value


def main():
    basicConfig(
        level=logging.WARNING,
        stream=sys.stderr,
    )

    StepLogger.start()
    processwrapper.enable_logging()

    # Support both legacy variables and properly namespaced ones
    place = os.environ.get("PLACE", None)
    place = os.environ.get("LG_PLACE", place)
    state = os.environ.get("STATE", None)
    state = os.environ.get("LG_STATE", state)
    initial_state = os.environ.get("LG_INITIAL_STATE", None)
    token = os.environ.get("LG_TOKEN", None)

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-x",
        "--coordinator",
        metavar="ADDRESS",
        type=str,
        help="coordinator HOST[:PORT] (default: value from env variable LG_COORDINATOR, otherwise 127.0.0.1:20408)",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default=os.environ.get("LG_ENV"),
        help="env config file (default: value from env variable LG_ENV)",
    )
    parser.add_argument(
        "-p", "--place", type=str, default=place, help="place name/alias (default: value from env variable LG_PLACE)"
    )
    parser.add_argument(
        "-s",
        "--state",
        type=str,
        default=state,
        help="strategy state to switch into before command (default: value from env varibale LG_STATE)",
    )
    parser.add_argument(
        "-i",
        "--initial-state",
        type=str,
        default=initial_state,
        help="strategy state to force into before switching to desired state",
    )
    parser.add_argument(
        "-d", "--debug", action="store_true", default=False, help="enable debug mode (show python tracebacks)"
    )
    parser.add_argument("-v", "--verbose", action="count", default=0)
    parser.add_argument("-P", "--proxy", type=str, help="proxy connections via given ssh host")
    subparsers = parser.add_subparsers(
        dest="command",
        title="available subcommands",
        metavar="COMMAND",
    )

    subparser = subparsers.add_parser("help")

    subparser = subparsers.add_parser("complete")
    subparser.add_argument("type", choices=["resources", "places", "matches", "match-names"])
    subparser.set_defaults(func=ClientSession.complete)

    subparser = subparsers.add_parser("monitor", help="monitor events from the coordinator")
    subparser.set_defaults(func=ClientSession.do_monitor)

    subparser = subparsers.add_parser("resources", aliases=("r",), help="list available resources")
    subparser.add_argument("-a", "--acquired", action="store_true")
    subparser.add_argument("-e", "--exporter")
    subparser.add_argument(
        "--sort-by-matched-place-change",
        action="store_true",
        help="sort by matched place's changed date (oldest first) and show place and date",
    )  # pylint: disable=line-too-long
    subparser.add_argument("match", nargs="?")
    subparser.set_defaults(func=ClientSession.print_resources)

    subparser = subparsers.add_parser("places", aliases=("p",), help="list available places")
    subparser.add_argument("-a", "--acquired", action="store_true")
    subparser.add_argument("-r", "--released", action="store_true")
    subparser.add_argument("--sort-last-changed", action="store_true", help="sort by last changed date (oldest first)")
    subparser.set_defaults(func=ClientSession.print_places)

    subparser = subparsers.add_parser("who", help="list acquired places by user")
    subparser.add_argument(
        "-e", "--show-exporters", action="store_true", help="show exporters currently used by each place"
    )
    subparser.set_defaults(func=ClientSession.print_who)

    subparser = subparsers.add_parser("show", help="show a place and related resources")
    subparser.set_defaults(func=ClientSession.print_place)

    subparser = subparsers.add_parser("create", help="add a new place")
    subparser.set_defaults(func=ClientSession.add_place)

    subparser = subparsers.add_parser("delete", help="delete an existing place")
    subparser.set_defaults(func=ClientSession.del_place)

    subparser = subparsers.add_parser("add-alias", help="add an alias to a place")
    subparser.add_argument("alias")
    subparser.set_defaults(func=ClientSession.add_alias)

    subparser = subparsers.add_parser("del-alias", help="delete an alias from a place")
    subparser.add_argument("alias")
    subparser.set_defaults(func=ClientSession.del_alias)

    subparser = subparsers.add_parser("set-comment", help="update the place comment")
    subparser.add_argument("comment", nargs="+")
    subparser.set_defaults(func=ClientSession.set_comment)

    subparser = subparsers.add_parser("set-tags", help="update the place tags")
    subparser.add_argument("tags", metavar="KEY=VALUE", nargs="+", help="use an empty value for deletion")
    subparser.set_defaults(func=ClientSession.set_tags)

    subparser = subparsers.add_parser("add-match", help="add one (or multiple) match pattern(s) to a place")
    subparser.add_argument("patterns", metavar="PATTERN", nargs="+")
    subparser.set_defaults(func=ClientSession.add_match)

    subparser = subparsers.add_parser("del-match", help="delete one (or multiple) match pattern(s) from a place")
    subparser.add_argument("patterns", metavar="PATTERN", nargs="+")
    subparser.set_defaults(func=ClientSession.del_match)

    subparser = subparsers.add_parser("add-named-match", help="add one match pattern with a name to a place")
    subparser.add_argument("pattern", metavar="PATTERN")
    subparser.add_argument("name", metavar="NAME")
    subparser.set_defaults(func=ClientSession.add_named_match)

    subparser = subparsers.add_parser("acquire", aliases=("lock",), help="acquire a place")
    subparser.add_argument(
        "--allow-unmatched", action="store_true", help="allow missing resources for matches when locking the place"
    )
    subparser.set_defaults(func=ClientSession.acquire)

    subparser = subparsers.add_parser("release", aliases=("unlock",), help="release a place")
    subparser.add_argument(
        "-k", "--kick", action="store_true", help="release a place even if it is acquired by a different user"
    )
    subparser.set_defaults(func=ClientSession.release)

    subparser = subparsers.add_parser(
        "release-from", help="atomically release a place, but only if locked by a specific user"
    )
    subparser.add_argument("acquired", metavar="HOST/USER", help="User and host to match against when releasing")
    subparser.set_defaults(func=ClientSession.release_from)

    subparser = subparsers.add_parser("allow", help="allow another user to access a place")
    subparser.add_argument("user", help="<host>/<username>")
    subparser.set_defaults(func=ClientSession.allow)

    subparser = subparsers.add_parser("env", help="generate a labgrid environment file for a place")
    subparser.set_defaults(func=ClientSession.print_env)

    subparser = subparsers.add_parser("power", aliases=("pw",), help="change (or get) a place's power status")
    subparser.add_argument("action", choices=["on", "off", "cycle", "get"])
    subparser.add_argument(
        "-t", "--delay", type=float, default=None, help="wait time in seconds between off and on during cycle"
    )
    subparser.add_argument("--name", "-n", help="optional resource name")
    subparser.set_defaults(func=ClientSession.power)

    subparser = subparsers.add_parser("io", help="change (or get) a digital IO status")
    subparser.add_argument("action", choices=["high", "low", "get"], help="action")
    subparser.add_argument("name", help="optional resource name", nargs="?")
    subparser.set_defaults(func=ClientSession.digital_io)

    subparser = subparsers.add_parser("console", aliases=("con",), help="connect to the console")
    subparser.add_argument(
        "-l", "--loop", action="store_true", help="keep trying to connect if the console is unavailable"
    )
    subparser.add_argument(
        "-o", "--listenonly", action="store_true", help="do not modify local terminal, do not send input from stdin"
    )
    subparser.add_argument("name", help="optional resource name", nargs="?")
    subparser.add_argument("--logfile", metavar="FILE", help="Log output to FILE", default=None)
    subparser.set_defaults(func=ClientSession.console)

    subparser = subparsers.add_parser("dfu", help="communicate with device in DFU mode")
    subparser.add_argument("action", choices=["download", "detach", "list"], help="action")
    subparser.add_argument("altsetting", help="altsetting name or number (download, detach only)", nargs="?")
    subparser.add_argument("filename", help="file to write into device (download only)", nargs="?")
    subparser.add_argument("--wait", type=float, default=10.0)
    subparser.add_argument("--name", "-n", help="optional resource name")
    subparser.set_defaults(func=ClientSession.dfu)

    subparser = subparsers.add_parser("fastboot", help="run fastboot")
    subparser.add_argument("fastboot_args", metavar="ARG", nargs=argparse.REMAINDER, help="fastboot arguments")
    subparser.add_argument("--wait", type=float, default=10.0)
    subparser.add_argument("--name", "-n", help="optional resource name")
    subparser.set_defaults(func=ClientSession.fastboot)

    subparser = subparsers.add_parser("flashscript", help="run flash script")
    subparser.add_argument("script", help="Flashing script")
    subparser.add_argument("script_args", metavar="ARG", nargs=argparse.REMAINDER, help="script arguments")
    subparser.add_argument("--name", "-n", help="optional resource name")
    subparser.set_defaults(func=ClientSession.flashscript)

    subparser = subparsers.add_parser("bootstrap", help="start a bootloader")
    subparser.add_argument("-w", "--wait", type=float, default=10.0)
    subparser.add_argument("filename", help="filename to boot on the target")
    subparser.add_argument("bootstrap_args", metavar="ARG", nargs=argparse.REMAINDER, help="extra bootstrap arguments")
    subparser.add_argument("--name", "-n", help="optional resource name")
    subparser.set_defaults(func=ClientSession.bootstrap)

    subparser = subparsers.add_parser("sd-mux", help="switch USB SD Muxer or get current mode")
    subparser.add_argument("action", choices=["dut", "host", "off", "client", "get"])
    subparser.add_argument("--name", "-n", help="optional resource name")
    subparser.set_defaults(func=ClientSession.sd_mux)

    subparser = subparsers.add_parser("usb-mux", help="switch USB Muxer")
    subparser.add_argument("links", choices=["off", "dut-device", "host-dut", "host-device", "host-dut+host-device"])
    subparser.add_argument("--name", "-n", help="optional resource name")
    subparser.set_defaults(func=ClientSession.usb_mux)

    subparser = subparsers.add_parser(
        "ssh",
        help="connect via ssh (with optional arguments)",
        epilog="Additional arguments are passed to the ssh subprocess.",
    )
    subparser.add_argument("--name", "-n", help="optional resource name")
    subparser.set_defaults(func=ClientSession.ssh)

    subparser = subparsers.add_parser("scp", help="transfer file via scp")
    subparser.add_argument("--name", "-n", help="optional resource name")
    subparser.add_argument("src", help="source path (use :dir/file for remote side)")
    subparser.add_argument("dst", help="destination path (use :dir/file for remote side)")
    subparser.set_defaults(func=ClientSession.scp)

    subparser = subparsers.add_parser(
        "rsync", help="transfer files via rsync", epilog="Additional arguments are passed to the rsync subprocess."
    )
    subparser.add_argument("--name", "-n", help="optional resource name")
    subparser.add_argument("src", help="source path (use :dir/file for remote side)")
    subparser.add_argument("dst", help="destination path (use :dir/file for remote side)")
    subparser.set_defaults(func=ClientSession.rsync)

    subparser = subparsers.add_parser("sshfs", help="mount via sshfs (blocking)")
    subparser.add_argument("--name", "-n", help="optional resource name")
    subparser.add_argument("path", help="remote path on the target")
    subparser.add_argument("mountpoint", help="local path")
    subparser.set_defaults(func=ClientSession.sshfs)

    subparser = subparsers.add_parser("forward", help="forward local port to remote target")
    subparser.add_argument("--name", "-n", help="optional resource name")
    subparser.add_argument(
        "--local",
        "-L",
        metavar="[LOCAL:]REMOTE",
        action=LocalPort,
        help="Forward local port LOCAL to remote port REMOTE. If LOCAL is unspecified, an arbitrary port will be chosen",
    )
    subparser.add_argument(
        "--remote",
        "-R",
        metavar="REMOTE:LOCAL",
        action=RemotePort,
        help="Forward remote port REMOTE to local port LOCAL",
    )
    subparser.set_defaults(func=ClientSession.forward)

    subparser = subparsers.add_parser("telnet", help="connect via telnet")
    subparser.set_defaults(func=ClientSession.telnet)

    subparser = subparsers.add_parser("video", help="start a video stream")
    subparser.add_argument("-q", "--quality", type=str, help="select a video quality (use 'list' to show options)")
    subparser.add_argument(
        "-c", "--controls", type=str, help="configure v4l controls (such as 'focus_auto=0,focus_absolute=40')"
    )
    subparser.add_argument("--name", "-n", help="optional resource name")
    subparser.set_defaults(func=ClientSession.video)

    subparser = subparsers.add_parser("audio", help="start a audio stream")
    subparser.add_argument("--name", "-n", help="optional resource name")
    subparser.set_defaults(func=ClientSession.audio)

    tmc_parser = subparsers.add_parser("tmc", help="control a USB TMC device")
    tmc_parser.add_argument("--name", "-n", help="optional resource name")
    tmc_parser.set_defaults(func=lambda _: tmc_parser.print_help(file=sys.stderr))
    tmc_subparsers = tmc_parser.add_subparsers(
        dest="subcommand",
        title="available subcommands",
        metavar="SUBCOMMAND",
    )

    tmc_subparser = tmc_subparsers.add_parser("cmd", aliases=("c",), help="execute raw command")
    tmc_subparser.add_argument("command", nargs="+")
    tmc_subparser.set_defaults(func=ClientSession.tmc_command)

    tmc_subparser = tmc_subparsers.add_parser("query", aliases=("q",), help="execute raw query")
    tmc_subparser.add_argument("query", nargs="+")
    tmc_subparser.set_defaults(func=ClientSession.tmc_query)

    tmc_subparser = tmc_subparsers.add_parser("screen", help="show or save a screenshot")
    tmc_subparser.add_argument("action", choices=["show", "save"])
    tmc_subparser.set_defaults(func=ClientSession.tmc_screen)

    tmc_subparser = tmc_subparsers.add_parser("channel", help="use a channel")
    tmc_subparser.add_argument("channel", type=int)
    tmc_subparser.add_argument("action", choices=["info", "values"])
    tmc_subparser.set_defaults(func=ClientSession.tmc_channel)

    subparser = subparsers.add_parser(
        "write-files",
        help="copy files onto mass storage device",
        usage="%(prog)s [OPTION]... -T SOURCE DEST\n" + "       %(prog)s [OPTION]... [-t DIRECTORY] SOURCE...",
    )
    subparser.add_argument("-w", "--wait", type=float, default=10.0, help="storage poll timeout in seconds")
    subparser.add_argument(
        "-p",
        "--partition",
        type=int,
        choices=range(0, 256),
        metavar="0-255",
        default=1,
        help="partition number to mount or 0 to mount whole disk (default: %(default)s)",
    )
    group = subparser.add_mutually_exclusive_group()
    group.add_argument(
        "-t",
        "--target-directory",
        type=pathlib.PurePath,
        metavar="DIRECTORY",
        default=pathlib.PurePath("/"),
        help="copy all SOURCE files into DIRECTORY (default: partition root)",
    )
    group.add_argument("-T", action="store_true", dest="rename", help="copy SOURCE file and rename to DEST")
    subparser.add_argument("--name", "-n", help="optional resource name")
    subparser.add_argument("SOURCE", type=pathlib.PurePath, nargs="+", help="source file(s) to copy")
    subparser.add_argument("DEST", type=pathlib.PurePath, nargs="?", help="destination file name for SOURCE")
    subparser.set_defaults(func=ClientSession.write_files, parser=subparser)

    subparser = subparsers.add_parser("write-image", help="write an image onto mass storage")
    subparser.add_argument("-w", "--wait", type=float, default=10.0)
    subparser.add_argument("-p", "--partition", type=int, help="partition number to write to")
    subparser.add_argument("--skip", type=int, default=0, help="skip n 512-sized blocks at start of input")
    subparser.add_argument("--seek", type=int, default=0, help="skip n 512-sized blocks at start of output")
    subparser.add_argument(
        "--mode",
        dest="write_mode",
        type=Mode,
        choices=Mode,
        default=Mode.DD,
        help="Choose tool for writing images (default: %(default)s)",
    )
    subparser.add_argument("--name", "-n", help="optional resource name")
    subparser.add_argument("filename", help="filename to boot on the target")
    subparser.set_defaults(func=ClientSession.write_image)

    subparser = subparsers.add_parser("reserve", help="create a reservation")
    subparser.add_argument("--wait", action="store_true", help="wait until the reservation is allocated")
    subparser.add_argument("--shell", action="store_true", help="format output as shell variables")
    subparser.add_argument(
        "--prio", type=float, default=0.0, help="priority relative to other reservations (default 0)"
    )
    subparser.add_argument("filters", metavar="KEY=VALUE", nargs="+", help="required tags")
    subparser.set_defaults(func=ClientSession.create_reservation)

    subparser = subparsers.add_parser("cancel-reservation", help="cancel a reservation")
    subparser.add_argument("token", type=str, default=token, nargs="?" if token else None)
    subparser.set_defaults(func=ClientSession.cancel_reservation)

    subparser = subparsers.add_parser("wait", help="wait for a reservation to be allocated")
    subparser.add_argument("token", type=str, default=token, nargs="?" if token else None)
    subparser.set_defaults(func=ClientSession.wait_reservation)

    subparser = subparsers.add_parser("reservations", help="list current reservations")
    subparser.set_defaults(func=ClientSession.print_reservations)

    subparser = subparsers.add_parser(
        "export", help="export driver information to a file (needs environment with drivers)"
    )
    subparser.add_argument(
        "--format",
        dest="format",
        type=ExportFormat,
        choices=ExportFormat,
        default=ExportFormat.SHELL_EXPORT,
        help="output format (default: %(default)s)",
    )
    subparser.add_argument("filename", help="output filename")
    subparser.set_defaults(func=ClientSession.export)

    subparser = subparsers.add_parser("version", help="show version")
    subparser.set_defaults(func=ClientSession.print_version)

    # make any leftover arguments available for some commands
    args, leftover = parser.parse_known_args()
    if args.command not in ["ssh", "rsync", "forward"]:
        args = parser.parse_args()
    else:
        args.leftover = leftover

    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)
    if args.verbose > 1:
        logging.getLogger().setLevel(logging.CONSOLE)
    if args.debug or args.verbose > 2:
        logging.getLogger().setLevel(logging.DEBUG)

    if not args.config and (args.state or args.initial_state):
        print("Setting the state requires a configuration file", file=sys.stderr)
        exit(1)
    if args.initial_state and not args.state:
        print("Setting the initial state requires a desired state", file=sys.stderr)
        exit(1)

    if args.proxy:
        proxymanager.force_proxy(args.proxy)

    env = None
    if args.config:
        env = Environment(config_file=args.config)

    role = None
    if args.command != "reserve" and env and env.config.get_targets():
        if args.place:
            if not args.place.startswith("+"):
                role = find_role_by_place(env.config.get_targets(), args.place)
                if not role:
                    print(f"RemotePlace {args.place} not found in configuration file", file=sys.stderr)
                    exit(1)
                print(f"Selected role {role} from configuration file")
        else:
            role, args.place = find_any_role_with_place(env.config.get_targets())
            if not role:
                print("No RemotePlace found in configuration file", file=sys.stderr)
                exit(1)
            print(f"Selected role {role} and place {args.place} from configuration file")

    extra = {
        "args": args,
        "env": env,
        "role": role,
        "prog": parser.prog,
    }

    if args.command and args.command != "help":
        exitcode = 0
        try:
            signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

            try:
                coordinator_address = args.coordinator or env.config.get_option("coordinator_address")
            except (AttributeError, KeyError):
                # in case of no env or not set, use LG_COORDINATOR env variable or default
                coordinator_address = os.environ.get("LG_COORDINATOR", "127.0.0.1:20408")

            logging.debug('Starting session with "%s"', coordinator_address)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            session = start_session(coordinator_address, extra=extra, debug=args.debug, loop=loop)
            logging.debug("Started session")

            try:
                if asyncio.iscoroutinefunction(args.func):
                    if getattr(args.func, "needs_target", False):
                        place = session.get_acquired_place()
                        target = session._get_target(place)
                        coro = args.func(session, place, target)
                    else:
                        coro = args.func(session)
                    session.loop.run_until_complete(coro)
                else:
                    args.func(session)
            finally:
                logging.debug("Stopping session")
                session.loop.run_until_complete(session.stop())
                session.loop.run_until_complete(session.close())
                logging.debug("Stopping loop")
                session.loop.close()
        except (NoResourceFoundError, NoDriverFoundError, InvalidConfigError) as e:
            if args.debug:
                traceback.print_exc(file=sys.stderr)
            else:
                print(f"{parser.prog}: error: {e}", file=sys.stderr)

            if isinstance(e, NoResourceFoundError):
                if e.found:
                    print("Found multiple resources but no name was given, available names:", file=sys.stderr)
                    for res in e.found:
                        print(f"{res.name}", file=sys.stderr)
                else:
                    print(
                        "This may be caused by disconnected exporter or wrong match entries.\nYou can use the 'show' command to review all matching resources.",
                        file=sys.stderr,
                    )  # pylint: disable=line-too-long
            elif isinstance(e, NoDriverFoundError):
                print(
                    "This is likely caused by an error or missing driver in the environment configuration.",
                    file=sys.stderr,
                )  # pylint: disable=line-too-long
            elif isinstance(e, InvalidConfigError):
                print(
                    "This is likely caused by an error in the environment configuration or invalid\nresource information provided by the coordinator.",
                    file=sys.stderr,
                )  # pylint: disable=line-too-long

            exitcode = 1
        except ServerError as e:
            print(f"Server error: {e}", file=sys.stderr)
            exitcode = 1
        except InteractiveCommandError as e:
            if args.debug:
                traceback.print_exc(file=sys.stderr)
            exitcode = e.exitcode
        except Error as e:
            if args.debug:
                traceback.print_exc(file=sys.stderr)
            else:
                print(f"{parser.prog}: error: {e}", file=sys.stderr)
            exitcode = 1
        except KeyboardInterrupt:
            exitcode = 1
        except Exception:  # pylint: disable=broad-except
            traceback.print_exc(file=sys.stderr)
            exitcode = 2
        exit(exitcode)
    else:
        parser.print_help(file=sys.stderr)


if __name__ == "__main__":
    main()
