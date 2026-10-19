"""The remote.client module contains the functionality to connect to a
coordinator, acquire a place and interact with the connected resources"""

import argparse
import asyncio
import contextlib
import enum
import ipaddress
import json
import logging
import os
import pathlib
import shlex
import shutil
import signal
import subprocess
import sys
import traceback
from collections import OrderedDict, defaultdict
from datetime import datetime
from pprint import pformat
from socket import gethostbyname
from textwrap import indent

import attr

from .. import Environment, Target, target_factory
from ..driver import ExecutionError, Mode
from ..exceptions import InvalidConfigError, NoDriverFoundError, NoResourceFoundError
from ..logging import StepLogger, basicConfig
from ..resource.remote import RemotePlace
from ..util import Timeout, atomic_replace, diff_dict, dump, flat_dict, labgrid_version
from ..util.helper import processwrapper
from ..util.proxy import proxymanager
from ..util.ssh import sshmanager
from .common import (
    TAG_KEY,
    TAG_VAL,
    ReservationState,
    ResourceMatch,
    get_client_credentials,
)
from .session import ClientSession as ClientSession  # pylint: disable=unused-import
from .session import (
    Error,
    ErrorGroup,
    MissingPlaceNameError,
    PlaceHostMismatchError,
    PlaceReleasePermissionError,
    PlaceUserMismatchError,
    ReservationFilter,
    ResourceChanged,
    ServerError,
    Tag,
    UserError,
)
from .session import ensure_event_loop as ensure_event_loop  # pylint: disable=unused-import
from .session import start_session as start_library_session

# This is a workaround for https://github.com/grpc/grpc/issues/38679.
# Since Python 3.12, gRPC can print an empty exception during shutdown.
sys.excepthook = lambda type, value, traceback: sys.__excepthook__(type, value, traceback)


class InteractiveCommandError(Error):
    def __init__(self: Error, msg: str, exitcode: int):
        super(InteractiveCommandError, self).__init__(msg)
        self.exitcode = exitcode


def _get_reservation_id_from_env():
    reservation_id = os.environ.get("LG_RESERVATION")
    legacy_reservation_id = os.environ.get("LG_TOKEN")
    if reservation_id:
        if legacy_reservation_id and legacy_reservation_id != reservation_id:
            print(
                "warning: LG_RESERVATION and deprecated LG_TOKEN are set to different values; using LG_RESERVATION",
                file=sys.stderr,
            )
        return reservation_id

    if legacy_reservation_id:
        print("warning: LG_TOKEN is deprecated; use LG_RESERVATION instead", file=sys.stderr)
    return legacy_reservation_id


@attr.s(eq=False)
class ClientCommands:
    """Command-line parsing adapters, presenters and interactive commands."""

    session = attr.ib()
    args = attr.ib()
    prog = attr.ib(default=None)

    def __getattr__(self, name):
        return getattr(self.session, name)

    def _print_event(self, event):
        if isinstance(event, ResourceChanged):
            exporter, group_name, resource_name = event.exporter, event.group, event.name
            resource = event.current.data if event.current else {}
            old = event.previous.data if event.previous else None
            if "cls" in resource and not old:
                print(f"Resource {exporter}/{group_name}/{resource['cls']}/{resource_name} created: {resource}")
            elif "cls" in resource and old:
                print(f"Resource {exporter}/{group_name}/{resource['cls']}/{resource_name} changed:")
                for k, v_old, v_new in diff_dict(flat_dict(old), flat_dict(resource)):
                    print(f"  {k}: {v_old} -> {v_new}")
            else:
                print(f"Resource {exporter}/{group_name}/???/{resource_name} deleted")
        elif event.current is None:
            print(f"Place {event.name} deleted")
        elif event.previous is None:
            print(f"Place {event.name} created: {event.description}")
        else:
            print(f"Place {event.name} changed:")
            for k, v_old, v_new in diff_dict(flat_dict(event.previous.asdict()), flat_dict(event.current.asdict())):
                print(f"  {k}: {v_old} -> {v_new}")

    async def do_monitor(self):
        self.session.subscribe(self._print_event)
        try:
            await self.stopping.wait()
        finally:
            self.session.unsubscribe(self._print_event)

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
        try:
            match = ResourceMatch.fromstr(self.args.match) if self.args.match else None
        except ValueError as e:
            raise UserError(str(e)) from e

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
        result[1:] = sorted(result[1:])

        widths = [max(map(len, c)) for c in zip(*result)]
        layout = []
        for i, w in enumerate(widths):
            layout.append("{%i:<%is}" % (i, w))
        layout = "  ".join(layout)

        for entry in result:
            print(layout.format(*entry))

    def get_place(self, place=None):
        return self.session.get_place(place or self.args.place)

    def get_idle_place(self, place=None):
        return self.session.get_idle_place(place or self.args.place)

    def get_acquired_place(self, place=None):
        place = self.get_place(place)
        try:
            return self.session.get_acquired_place(place)
        except (PlaceUserMismatchError, PlaceHostMismatchError) as exc:
            command = f"labgrid-client -p {exc.place_name} allow {self.gethostname()}/{self.getuser()}"
            if isinstance(exc, PlaceUserMismatchError):
                hint = f"To work simultaneously, {exc.owner_user} can execute {command}"
            else:
                hint = f"To allow this host, use {command} on the other host"
            raise UserError(f"{exc.args[0]} {hint}") from None

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
        try:
            await self.session.add_place(self.args.place)
        except MissingPlaceNameError as exc:
            raise UserError(f"{exc.args[0]}. Set with -p <place> or via env var LG_PLACE") from None

    async def del_place(self):
        await self.session.del_place(self.get_idle_place())

    async def add_alias(self):
        await self.session.add_alias(self.get_idle_place(), self.args.alias)

    async def del_alias(self):
        await self.session.del_alias(self.get_idle_place(), self.args.alias)

    async def set_comment(self):
        await self.session.set_comment(self.get_place(), " ".join(self.args.comment))

    async def set_tags(self):
        """Set the tags on a place"""
        place = self.get_place()
        tags = []
        for pair in self.args.tags:
            try:
                k, v = pair.split("=")
            except ValueError:
                raise UserError(f"tag '{pair}' needs to match '<key>=<value>'")
            if not TAG_KEY.match(k):
                raise UserError(f"tag key '{k}' needs to match the rexex '{TAG_KEY.pattern}'")
            if not TAG_VAL.match(v):
                raise UserError(f"tag value '{v}' needs to match the rexex '{TAG_VAL.pattern}'")
            tags.append(Tag(k, v))

        await self.session.set_tags(place, tags)

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

            await self.session.add_match(place, ResourceMatch.fromstr(pattern))

    async def del_match(self):
        """Delete a match for a place"""
        place = self.get_idle_place()
        for pattern in self.args.patterns:
            if not 2 <= pattern.count("/") <= 3:
                raise UserError(f"invalid pattern format '{pattern}' (use 'exporter/group/cls/name')")
            if not place.hasmatch(pattern.split("/")):
                print(f"pattern '{pattern}' not found, skipping", file=sys.stderr)

            await self.session.del_match(place, ResourceMatch.fromstr(pattern))

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

        match = ResourceMatch.fromstr(pattern)
        match.rename = name
        await self.session.add_match(place, match)

    async def acquire(self):
        errors = []
        places = self.get_place_names_from_env() if self.env else [self.args.place]
        for place in places:
            try:
                await self._acquire_place(place)
            except Error as e:
                errors.append(e)

        if errors:
            if len(errors) == 1:
                raise errors[0]
            raise ErrorGroup("Multiple errors occurred during acquire", errors)

    async def _acquire_place(self, place):
        place = self.get_place(place)
        try:
            await self.session.acquire_place(place, allow_unmatched=self.args.allow_unmatched)
            print(f"acquired place {place.name}")
        except (PlaceUserMismatchError, PlaceHostMismatchError) as exc:
            command = (
                f"'labgrid-client -p {exc.place_name} allow {self.gethostname()}/{self.getuser()}' "
                f"on {exc.owner_host}."
            )
            hint = "To work simultaneously, "
            hint += (
                f"execute {command}"
                if isinstance(exc, PlaceHostMismatchError)
                else f"{exc.owner_user} can execute {command}"
            )
            raise UserError(f"{exc.args[0]} {hint}") from None

    async def release(self):
        errors = []
        places = self.get_place_names_from_env() if self.env else [self.args.place]
        for place in places:
            try:
                await self._release_place(place)
            except Error as e:
                errors.append(e)

        if errors:
            if len(errors) == 1:
                raise errors[0]
            raise ErrorGroup("Multiple errors occurred during release", errors)

    async def _release_place(self, place):
        """Release a previously acquired place"""
        place = self.get_place(place)
        if place.acquired and self.args.kick and place.acquired.split("/")[1] != self.getuser():
            print(f"warning: kicking user ({place.acquired})")

        try:
            await self.session.release_place(place, kick=self.args.kick)
        except PlaceReleasePermissionError as exc:
            raise UserError(f"{exc.args[0]}, use --kick if you are sure") from None
        print(f"released place {place.name}")

    async def release_from(self):
        place = await self.session.release_from(self.get_place(), self.args.acquired)
        print(f"{self.args.acquired} has released place {place.name}")

    async def allow(self):
        place = self.get_acquired_place()
        await self.session.allow(place, self.args.user)
        print(f"allowed {self.args.user} for place {place.name}")

    def get_target_config(self, place):
        config = {}
        resources = config["resources"] = []
        for binding in self.session.get_target_resources(place):
            name, resource = binding.name, binding.resource
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

    def _get_target(self, place):
        self.session._prepare_manager()
        target = None
        if self.env:
            if self.session.role is None:
                self.session.role = find_role_by_place(self.env.config.get_targets(), place.name)
                if self.session.role is not None:
                    print(f"Selected role {self.session.role} from configuration file")
            target = self.env.get_target(self.session.role)
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
        from ..resource import NetworkYKUSHPowerPort, TasmotaPowerPort
        from ..resource.power import NetworkPowerPort, PDUDaemonPort
        from ..resource.remote import NetworkSiSPMPowerPort, NetworkSysfsGPIO, NetworkUSBPowerPort

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
        from ..resource import (
            Eth008DigitalOutput,
            HttpDigitalOutput,
            ModbusTCPCoil,
            OneWirePIO,
            WaveshareModbusTCPCoil,
        )
        from ..resource.remote import (
            NetworkDeditecRelais8,
            NetworkFTDIGPIO,
            NetworkHIDRelay,
            NetworkLXAIOBusPIO,
            NetworkSysfsGPIO,
        )

        drv = None
        try:
            if action == "get":
                drv = target.get_driver("DigitalInputProtocol", name=name)
            else:
                drv = target.get_driver("DigitalOutputProtocol", name=name)
        except NoDriverFoundError:
            for resource in target.resources:
                if name and resource.name != name:
                    continue
                if isinstance(resource, WaveshareModbusTCPCoil):
                    drv = self._get_driver_or_new(target, "WaveShareModbusCoilDriver", name=name)
                elif isinstance(resource, ModbusTCPCoil):
                    drv = self._get_driver_or_new(target, "ModbusCoilDriver", name=name)
                elif isinstance(resource, Eth008DigitalOutput):
                    drv = self._get_driver_or_new(target, "Eth008DigitalOutputDriver", name=name)
                elif isinstance(resource, OneWirePIO):
                    drv = self._get_driver_or_new(target, "OneWirePIODriver", name=name)
                elif isinstance(resource, HttpDigitalOutput):
                    drv = self._get_driver_or_new(target, "HttpDigitalOutputDriver", name=name)
                elif isinstance(resource, NetworkDeditecRelais8):
                    drv = self._get_driver_or_new(target, "DeditecRelaisDriver", name=name)
                elif isinstance(resource, NetworkSysfsGPIO):
                    drv = self._get_driver_or_new(target, "GpioDigitalOutputDriver", name=name)
                elif isinstance(resource, NetworkFTDIGPIO):
                    drv = self._get_driver_or_new(target, "FTDIGPIODriver", name=name)
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

            self.logger.info("microcom not available, using telnet instead")

            if listen_only:
                self.logger.warning("--listenonly option not supported by telnet, ignoring")

            if logfile:
                self.logger.warning("--logfile option not supported by telnet, ignoring")

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
                    raise InteractiveCommandError("microcom error", res)
                break
            await asyncio.sleep(1.0)

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
        from ..driver import OpenOCDDriver
        from ..resource.remote import (
            NetworkAlteraUSBBlaster,
            NetworkIMXUSBLoader,
            NetworkMXSUSBLoader,
            NetworkRKUSBLoader,
        )

        drv = None
        try:
            drv = target.get_driver("BootstrapProtocol", name=name)
        except NoDriverFoundError:
            for resource in target.resources:
                if name and resource.name != name:
                    continue
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
        from ..resource.remote import NetworkUSBSDMuxDevice, NetworkUSBSDWire3Device, NetworkUSBSDWireDevice

        drv = None
        for resource in target.resources:
            if name and resource.name != name:
                continue
            if isinstance(resource, NetworkUSBSDMuxDevice):
                drv = self._get_driver_or_new(target, "USBSDMuxDriver", name=name)
            elif isinstance(resource, NetworkUSBSDWireDevice):
                drv = self._get_driver_or_new(target, "USBSDWireDriver", name=name)
            elif isinstance(resource, NetworkUSBSDWire3Device):
                drv = self._get_driver_or_new(target, "USBSDWire3Driver", name=name)
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
            if name and resource.name != name:
                continue
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
            raise InteractiveCommandError("ssh error", res)

    def scp(self):
        drv = self._get_ssh()

        res = drv.scp(src=self.args.src, dst=self.args.dst)
        if res:
            raise InteractiveCommandError("scp error", res)

    def rsync(self):
        drv = self._get_ssh()

        res = drv.rsync(src=self.args.src, dst=self.args.dst, extra=self.args.leftover)
        if res:
            raise InteractiveCommandError("rsync error", res)

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
            raise InteractiveCommandError("telnet error", res)

    def video(self):
        place = self.get_acquired_place()
        quality = self.args.quality
        controls = self.args.controls
        target = self._get_target(place)
        name = self.args.name
        from ..resource.httpvideostream import HTTPVideoStream
        from ..resource.remote import NetworkUSBVideo
        from ..resource.udev import USBVideo

        drv = None
        try:
            drv = target.get_driver("VideoProtocol", name=name)
        except NoDriverFoundError:
            for resource in target.resources:
                if name and resource.name != name:
                    continue
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
                raise InteractiveCommandError("gst-launch-1.0 error", res)

    def audio(self):
        place = self.get_acquired_place()
        target = self._get_target(place)
        name = self.args.name
        drv = self._get_driver_or_new(target, "USBAudioInputDriver", name=name)
        res = drv.play()
        if res:
            raise InteractiveCommandError("gst-launch-1.0 error", res)

    def netns(self):
        place = self.get_acquired_place()
        with self._get_target(place) as target:
            name = self.args.name
            drv = self._get_driver_or_new(target, "RawNetworkInterfaceDriver", name=name)
            with drv.setup_netns(self.args.mac_address) as ns:
                for a in self.args.address:
                    ns.run(["ip", "addr", "add", str(a), "dev", ns.intf], check=True)

                if self.args.nsenter:
                    with open(self.args.nsenter, "w") as wrapper:
                        wrapper.write(
                            "\n".join(
                                [
                                    "#!/usr/bin/sh",
                                    " ".join(ns.prefix) + ' "$@"',
                                    "",
                                ]
                            )
                        )
                        os.fchmod(wrapper.fileno(), 0o755)
                    print(f"Use {self.args.nsenter} to enter the namespace")

                cmd = self.args.cmd
                if not cmd:
                    # Same behavior as nsenter with no command
                    cmd = os.environ.get("SHELL", "/bin/sh")

                p = ns.run(cmd)
                if p.returncode != 0:
                    raise InteractiveCommandError("netns command error", p.returncode)

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

        tags = []
        for pair in self.args.filters:
            try:
                k, v = pair.split("=")
            except ValueError:
                raise UserError(f"'{pair}' is not a valid filter (must contain a '=')")
            if not TAG_KEY.match(k):
                raise UserError(f"Key '{k}' in filter '{pair}' is invalid")
            if not TAG_VAL.match(v):
                raise UserError(f"Value '{v}' in filter '{pair}' is invalid")
            tags.append(Tag(k, v))

        res = await self.session.create_reservation((ReservationFilter("main", tuple(tags)),), prio)
        if self.args.shell:
            print(f"export LG_RESERVATION={res.id}")
            # TODO: remove the deprecated LG_TOKEN export after one release.
            print(f"export LG_TOKEN={res.id}")
        else:
            print(f"Reservation '{res.id}':")
            res.show(level=1)
        if self.args.wait:
            if not self.args.shell:
                print("Waiting for allocation...")
            await self._wait_reservation(res.id, verbose=False)

    async def cancel_reservation(self):
        await self.session.cancel_reservation(self.args.reservation_id)

    async def _wait_reservation(self, reservation_id: str, verbose=True):
        while True:
            res = await self.session.poll_reservation(reservation_id)
            if verbose:
                res.show()
            if res.state is ReservationState.waiting:
                await asyncio.sleep(1.0)
            else:
                break

    async def wait_reservation(self):
        reservation_id = self.args.reservation_id
        await self._wait_reservation(reservation_id)

    async def print_reservations(self):
        reservations = await self.session.list_reservations()

        for res in sorted(reservations, key=lambda x: (-x.prio, x.created)):
            print(f"Reservation '{res.id}':")
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

    def print_version(self):
        print(labgrid_version())

    def adb(self):
        place = self.get_acquired_place()
        target = self._get_target(place)
        name = self.args.name
        adb_cmd = ["adb"]

        from ..resource.adb import NetworkADBDevice, RemoteUSBADBDevice

        for resource in target.resources:
            if name and resource.name != name:
                continue
            if isinstance(resource, RemoteUSBADBDevice):
                host, port = proxymanager.get_host_and_port(resource)
                adb_cmd = ["adb", "-H", host, "-P", str(port), "-s", resource.serialno]
                break
            elif isinstance(resource, NetworkADBDevice):
                host, port = proxymanager.get_host_and_port(resource)
                # ADB does not automatically remove a network device from its
                # devices list when the connection is broken by the remote, so the
                # adb connection may have gone "stale", resulting in adb blocking
                # indefinitely when making calls to the device. To avoid this,
                # always disconnect first.
                subprocess.run(
                    ["adb", "disconnect", f"{host}:{str(port)}"], stderr=subprocess.DEVNULL, timeout=10, check=True
                )
                subprocess.run(
                    ["adb", "connect", f"{host}:{str(port)}"], stdout=subprocess.DEVNULL, timeout=10, check=True
                )  # Connect adb client to TCP adb device
                adb_cmd = ["adb", "-s", f"{host}:{str(port)}"]
                break

        adb_cmd += self.args.leftover
        subprocess.run(adb_cmd, check=True)

    def scrcpy(self):
        place = self.get_acquired_place()
        target = self._get_target(place)
        name = self.args.name
        scrcpy_cmd = ["scrcpy"]
        env_var = os.environ.copy()

        from ..resource.adb import NetworkADBDevice, RemoteUSBADBDevice

        for resource in target.resources:
            if name and resource.name != name:
                continue
            if isinstance(resource, RemoteUSBADBDevice):
                host, adb_port = proxymanager.get_host_and_port(resource)
                ip_addr = gethostbyname(host)
                env_var["ADB_SERVER_SOCKET"] = f"tcp:{ip_addr}:{adb_port}"

                # Find a free port on the exporter machine
                scrcpy_port = sshmanager.get(host).run_check(
                    'python -c "'
                    "import socket;"
                    "s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.bind(("
                    "'', 0));"
                    "addr = s.getsockname();"
                    "print(addr[1]);"
                    's.close()"'
                )[0]

                scrcpy_cmd = [
                    "scrcpy",
                    "--port",
                    scrcpy_port,
                    "-s",
                    resource.serialno,
                ]

                # If a proxy is required, we need to setup a ssh port forward for the port
                # (27183) scrcpy will use to send data along side the adb port
                if resource.extra.get("proxy_required") or self.args.proxy:
                    proxy = resource.extra.get("proxy")
                    scrcpy_cmd.append(f"--tunnel-host={ip_addr}")
                    scrcpy_cmd.append(f"--tunnel-port={sshmanager.request_forward(proxy, host, int(scrcpy_port))}")
                break

            elif isinstance(resource, NetworkADBDevice):
                host, port = proxymanager.get_host_and_port(resource)
                # ADB does not automatically remove a network device from its
                # devices list when the connection is broken by the remote, so the
                # adb connection may have gone "stale", resulting in adb blocking
                # indefinitely when making calls to the device. To avoid this,
                # always disconnect first.
                subprocess.run(
                    ["adb", "disconnect", f"{host}:{str(port)}"], stderr=subprocess.DEVNULL, timeout=10, check=True
                )
                scrcpy_cmd = ["scrcpy", f"--tcpip={host}:{str(port)}"]
                break

        scrcpy_cmd += self.args.leftover
        subprocess.run(scrcpy_cmd, env=env_var, check=True)


ClientCommands.console.needs_target = True
ClientCommands.export.needs_target = True


def start_session(address, *, extra=None, credentials=None, debug=False, loop=None):
    """Compatibility connection helper; new library callers use remote.session."""
    options = dict(extra or {})
    options.pop("args", None)
    options.pop("prog", None)
    options.setdefault("username", os.environ.get("LG_USERNAME"))
    options.setdefault("hostname", os.environ.get("LG_HOSTNAME"))
    if "reservation_id" not in options and "token" not in options:
        options["reservation_id"] = _get_reservation_id_from_env()
    return start_library_session(address, credentials=credentials, debug=debug, loop=loop, **options)


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


class AutoProgramArgumentParser(argparse.ArgumentParser):
    """Works around sphinxcontrib.autoprogram shortcomings."""

    class _ActionWrapper:
        """
        Wraps argparse's special private action object registered for "parsers", see:
        https://docs.python.org/3.14/library/argparse.html#argparse.ArgumentParser.add_subparsers
        https://docs.python.org/3.13/library/argparse.html#argparse.ArgumentParser.register
        """

        def __init__(self, action):
            self.action = action

        def add_parser(self, name, **kwargs):
            # aliases are not supported by autoprogram, they lead to duplicate entries, so
            # show them as "command subcommand|alias --option" instead
            aliases = kwargs.pop("aliases", [])
            if aliases:
                name = "|".join([name] + list(aliases))

            # "help" text is ignored by autoprogram, move to "description" instead
            if "description" not in kwargs and "help" in kwargs:
                kwargs["description"] = kwargs.pop("help")

            # add_parser() is the only part of the action object that's not an implementation detail
            return self.action.add_parser(name, **kwargs)

    def __init__(self, *args, **kwargs):
        # print help texts in fixed width
        os.environ["COLUMNS"] = "80"

        # hide --help, -h
        kwargs.setdefault("add_help", False)

        super().__init__(*args, **kwargs)

    def add_subparsers(self, **kwargs):
        action = super().add_subparsers(**kwargs)
        return self._ActionWrapper(action)

    def add_argument(self, *args, **kwargs):
        # do not show ranges
        if isinstance(kwargs.get("choices"), range):
            del kwargs["choices"]

        return super().add_argument(*args, **kwargs)


def get_parser(auto_doc_mode=False) -> "argparse.ArgumentParser | AutoProgramArgumentParser":
    # use custom parser for sphinxcontrib.autoprogram
    parser = AutoProgramArgumentParser() if auto_doc_mode else argparse.ArgumentParser()

    parser.add_argument(
        "-x",
        "--coordinator",
        metavar="ADDRESS",
        type=str,
        help="coordinator HOST[:PORT] (default: value from env variable LG_COORDINATOR, otherwise 127.0.0.1:20408)",
    )
    parser.add_argument(
        "--tls",
        action="store_true",
        default=os.environ.get("LG_COORDINATOR_TLS", "").strip().lower() in {"1", "true"},
        help="enable TLS gRPC channel",
    )
    parser.add_argument(
        "--cacert",
        type=pathlib.PurePath,
        help="path to CA certificate or CA bundle for verifying the coordinator (in PEM format)",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        help="env config file (default: value from env variable LG_ENV)",
    )
    parser.add_argument("-p", "--place", type=str, help="place name/alias (default: value from env variable LG_PLACE)")
    parser.add_argument(
        "-s",
        "--state",
        type=str,
        help="strategy state to switch into before command (default: value from env variable LG_STATE)",
    )
    parser.add_argument(
        "-i",
        "--initial-state",
        type=str,
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

    # if the argparse object is to be used for manpage generation, hide some subcommands
    if not auto_doc_mode:
        subparser = subparsers.add_parser("help")

        subparser = subparsers.add_parser("complete")
        subparser.add_argument("type", choices=["resources", "places", "matches", "match-names"])
        subparser.set_defaults(func=ClientCommands.complete)

    subparser = subparsers.add_parser("monitor", help="monitor events from the coordinator")
    subparser.set_defaults(func=ClientCommands.do_monitor)

    subparser = subparsers.add_parser("resources", aliases=("r",), help="list available resources")
    subparser.add_argument("-a", "--acquired", action="store_true")
    subparser.add_argument("-e", "--exporter")
    subparser.add_argument(
        "--sort-by-matched-place-change",
        action="store_true",
        help="sort by matched place's changed date (oldest first) and show place and date",
    )  # pylint: disable=line-too-long
    subparser.add_argument("match", nargs="?")
    subparser.set_defaults(func=ClientCommands.print_resources)

    subparser = subparsers.add_parser("places", aliases=("p",), help="list available places")
    subparser.add_argument("-a", "--acquired", action="store_true")
    subparser.add_argument("-r", "--released", action="store_true")
    subparser.add_argument("--sort-last-changed", action="store_true", help="sort by last changed date (oldest first)")
    subparser.set_defaults(func=ClientCommands.print_places)

    subparser = subparsers.add_parser("who", help="list acquired places by user")
    subparser.add_argument(
        "-e", "--show-exporters", action="store_true", help="show exporters currently used by each place"
    )
    subparser.set_defaults(func=ClientCommands.print_who)

    subparser = subparsers.add_parser("show", help="show a place and related resources")
    subparser.set_defaults(func=ClientCommands.print_place)

    subparser = subparsers.add_parser(
        "create",
        help="add a new place with the name specified via --place or the LG_PLACE environment variable",
    )
    subparser.set_defaults(func=ClientCommands.add_place)

    subparser = subparsers.add_parser("delete", help="delete an existing place")
    subparser.set_defaults(func=ClientCommands.del_place)

    subparser = subparsers.add_parser("add-alias", help="add an alias to a place")
    subparser.add_argument("alias")
    subparser.set_defaults(func=ClientCommands.add_alias)

    subparser = subparsers.add_parser("del-alias", help="delete an alias from a place")
    subparser.add_argument("alias")
    subparser.set_defaults(func=ClientCommands.del_alias)

    subparser = subparsers.add_parser("set-comment", help="update the place comment")
    subparser.add_argument("comment", nargs="+")
    subparser.set_defaults(func=ClientCommands.set_comment)

    subparser = subparsers.add_parser("set-tags", help="update the place tags")
    subparser.add_argument("tags", metavar="KEY=VALUE", nargs="+", help="use an empty value for deletion")
    subparser.set_defaults(func=ClientCommands.set_tags)

    subparser = subparsers.add_parser("add-match", help="add one (or multiple) match pattern(s) to a place")
    subparser.add_argument("patterns", metavar="PATTERN", nargs="+")
    subparser.set_defaults(func=ClientCommands.add_match)

    subparser = subparsers.add_parser("del-match", help="delete one (or multiple) match pattern(s) from a place")
    subparser.add_argument("patterns", metavar="PATTERN", nargs="+")
    subparser.set_defaults(func=ClientCommands.del_match)

    subparser = subparsers.add_parser("add-named-match", help="add one match pattern with a name to a place")
    subparser.add_argument("pattern", metavar="PATTERN")
    subparser.add_argument("name", metavar="NAME")
    subparser.set_defaults(func=ClientCommands.add_named_match)

    subparser = subparsers.add_parser("acquire", aliases=("lock",), help="acquire a place")
    subparser.add_argument(
        "--allow-unmatched", action="store_true", help="allow missing resources for matches when locking the place"
    )
    subparser.set_defaults(func=ClientCommands.acquire)

    subparser = subparsers.add_parser("release", aliases=("unlock",), help="release a place")
    subparser.add_argument(
        "-k", "--kick", action="store_true", help="release a place even if it is acquired by a different user"
    )
    subparser.set_defaults(func=ClientCommands.release)

    subparser = subparsers.add_parser(
        "release-from",
        help="atomically release a place, but only if locked by a specific user",
        epilog="Note that this command returns success as long as the specified user no longer owns the place, "
        "meaning it may be acquired by another user or not at all.",
    )
    subparser.add_argument("acquired", metavar="HOST/USER", help="User and host to match against when releasing")
    subparser.set_defaults(func=ClientCommands.release_from)

    subparser = subparsers.add_parser("allow", help="allow another user to access a place")
    subparser.add_argument("user", help="<host>/<username>")
    subparser.set_defaults(func=ClientCommands.allow)

    subparser = subparsers.add_parser("env", help="generate a labgrid environment file for a place")
    subparser.set_defaults(func=ClientCommands.print_env)

    subparser = subparsers.add_parser("power", aliases=("pw",), help="change (or get) a place's power status")
    subparser.add_argument("action", choices=["on", "off", "cycle", "get"])
    subparser.add_argument(
        "-t", "--delay", type=float, default=None, help="wait time in seconds between off and on during cycle"
    )
    subparser.add_argument("--name", "-n", help="optional resource name")
    subparser.set_defaults(func=ClientCommands.power)

    subparser = subparsers.add_parser("io", help="change (or get) a digital IO status")
    subparser.add_argument("action", choices=["high", "low", "get"], help="action")
    subparser.add_argument("name", help="optional resource name", nargs="?")
    subparser.set_defaults(func=ClientCommands.digital_io)

    subparser = subparsers.add_parser("console", aliases=("con",), help="connect to the console")
    subparser.add_argument(
        "-l", "--loop", action="store_true", help="keep trying to connect if the console is unavailable"
    )
    subparser.add_argument(
        "-o", "--listenonly", action="store_true", help="do not modify local terminal, do not send input from stdin"
    )
    subparser.add_argument("name", help="optional resource name", nargs="?")
    subparser.add_argument("--logfile", metavar="FILE", help="Log output to FILE", default=None)
    subparser.set_defaults(func=ClientCommands.console)

    subparser = subparsers.add_parser("dfu", help="communicate with device in DFU mode")
    subparser.add_argument("action", choices=["download", "detach", "list"], help="action")
    subparser.add_argument("altsetting", help="altsetting name or number (download, detach only)", nargs="?")
    subparser.add_argument("filename", help="file to write into device (download only)", nargs="?")
    subparser.add_argument("--wait", type=float, default=10.0)
    subparser.add_argument("--name", "-n", help="optional resource name")
    subparser.set_defaults(func=ClientCommands.dfu)

    subparser = subparsers.add_parser("fastboot", help="run fastboot")
    subparser.add_argument("fastboot_args", metavar="ARG", nargs=argparse.REMAINDER, help="fastboot arguments")
    subparser.add_argument("--wait", type=float, default=10.0)
    subparser.add_argument("--name", "-n", help="optional resource name")
    subparser.set_defaults(func=ClientCommands.fastboot)

    subparser = subparsers.add_parser("flashscript", help="Run arbitrary script with arguments to flash device")
    subparser.add_argument("script", help="Flashing script")
    subparser.add_argument("script_args", metavar="ARG", nargs=argparse.REMAINDER, help="script arguments")
    subparser.add_argument("--name", "-n", help="optional resource name")
    subparser.set_defaults(func=ClientCommands.flashscript)

    subparser = subparsers.add_parser("bootstrap", help="start a bootloader")
    subparser.add_argument("-w", "--wait", type=float, default=10.0)
    subparser.add_argument("filename", help="filename to boot on the target")
    subparser.add_argument("bootstrap_args", metavar="ARG", nargs=argparse.REMAINDER, help="extra bootstrap arguments")
    subparser.add_argument("--name", "-n", help="optional resource name")
    subparser.set_defaults(func=ClientCommands.bootstrap)

    subparser = subparsers.add_parser("sd-mux", help="switch USB SD Muxer or get current mode")
    subparser.add_argument("action", choices=["dut", "host", "off", "client", "get"])
    subparser.add_argument("--name", "-n", help="optional resource name")
    subparser.set_defaults(func=ClientCommands.sd_mux)

    subparser = subparsers.add_parser("usb-mux", help="switch USB Muxer")
    subparser.add_argument("links", choices=["off", "dut-device", "host-dut", "host-device", "host-dut+host-device"])
    subparser.add_argument("--name", "-n", help="optional resource name")
    subparser.set_defaults(func=ClientCommands.usb_mux)

    subparser = subparsers.add_parser(
        "ssh",
        help="connect via ssh (with optional arguments)",
        epilog="Additional arguments are passed to the ssh subprocess.",
    )
    subparser.add_argument("--name", "-n", help="optional resource name")
    subparser.set_defaults(func=ClientCommands.ssh)

    subparser = subparsers.add_parser("scp", help="transfer file via scp")
    subparser.add_argument("--name", "-n", help="optional resource name")
    subparser.add_argument("src", help="source path (use :dir/file for remote side)")
    subparser.add_argument("dst", help="destination path (use :dir/file for remote side)")
    subparser.set_defaults(func=ClientCommands.scp)

    subparser = subparsers.add_parser(
        "rsync", help="transfer files via rsync", epilog="Additional arguments are passed to the rsync subprocess."
    )
    subparser.add_argument("--name", "-n", help="optional resource name")
    subparser.add_argument("src", help="source path (use :dir/file for remote side)")
    subparser.add_argument("dst", help="destination path (use :dir/file for remote side)")
    subparser.set_defaults(func=ClientCommands.rsync)

    subparser = subparsers.add_parser("sshfs", help="mount via sshfs (blocking)")
    subparser.add_argument("--name", "-n", help="optional resource name")
    subparser.add_argument("path", help="remote path on the target")
    subparser.add_argument("mountpoint", help="local path")
    subparser.set_defaults(func=ClientCommands.sshfs)

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
    subparser.set_defaults(func=ClientCommands.forward)

    subparser = subparsers.add_parser("telnet", help="connect via telnet")
    subparser.set_defaults(func=ClientCommands.telnet)

    subparser = subparsers.add_parser("video", help="start a video stream")
    subparser.add_argument("-q", "--quality", type=str, help="select a video quality (use 'list' to show options)")
    subparser.add_argument(
        "-c", "--controls", type=str, help="configure v4l controls (such as 'focus_auto=0,focus_absolute=40')"
    )
    subparser.add_argument("--name", "-n", help="optional resource name")
    subparser.set_defaults(func=ClientCommands.video)

    subparser = subparsers.add_parser("audio", help="start a audio stream")
    subparser.add_argument("--name", "-n", help="optional resource name")
    subparser.set_defaults(func=ClientCommands.audio)

    subparser = subparsers.add_parser("netns", help="start a network namespace with access to NetworkInterface")
    subparser.add_argument("--name", "-n", help="optional resource name")
    subparser.add_argument(
        "--address",
        "-a",
        type=ipaddress.ip_interface,
        action="append",
        default=[],
        help="assign address to interface (CIDR notation)",
    )
    subparser.add_argument("--mac-address", help="assign MAC address to interface")
    subparser.add_argument(
        "--nsenter",
        "-e",
        nargs="?",
        default=False,
        const="labgrid-nsenter",
        help="create nsenter wrapper script",
    )
    subparser.add_argument(
        "cmd", nargs=argparse.REMAINDER, help="command to execute in the namespace. If unspecified, $SHELL is invoked"
    )
    subparser.set_defaults(func=ClientCommands.netns)

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
    tmc_subparser.set_defaults(func=ClientCommands.tmc_command)

    tmc_subparser = tmc_subparsers.add_parser("query", aliases=("q",), help="execute raw query")
    tmc_subparser.add_argument("query", nargs="+")
    tmc_subparser.set_defaults(func=ClientCommands.tmc_query)

    tmc_subparser = tmc_subparsers.add_parser("screen", help="show or save a screenshot")
    tmc_subparser.add_argument("action", choices=["show", "save"])
    tmc_subparser.set_defaults(func=ClientCommands.tmc_screen)

    tmc_subparser = tmc_subparsers.add_parser("channel", help="use a channel")
    tmc_subparser.add_argument("channel", type=int)
    tmc_subparser.add_argument("action", choices=["info", "values"])
    tmc_subparser.set_defaults(func=ClientCommands.tmc_channel)

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
    subparser.set_defaults(func=ClientCommands.write_files, parser=subparser)

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
    subparser.set_defaults(func=ClientCommands.write_image)

    subparser = subparsers.add_parser("reserve", help="create a reservation")
    subparser.add_argument("--wait", action="store_true", help="wait until the reservation is allocated")
    subparser.add_argument("--shell", action="store_true", help="format output as shell variables")
    subparser.add_argument(
        "--prio", type=float, default=0.0, help="priority relative to other reservations (default 0)"
    )
    subparser.add_argument("filters", metavar="KEY=VALUE", nargs="+", help="required tags")
    subparser.set_defaults(func=ClientCommands.create_reservation)

    subparser = subparsers.add_parser("cancel-reservation", help="cancel a reservation")
    subparser.add_argument(
        "reservation_id",
        type=str,
        nargs="?",
        help="the reservation id (previously called token)",
        metavar="reservation-id",
    )
    subparser.set_defaults(func=ClientCommands.cancel_reservation)

    subparser = subparsers.add_parser("wait", help="wait for a reservation to be allocated")
    subparser.add_argument(
        "reservation_id",
        type=str,
        nargs="?",
        help="the reservation id (previously called token)",
        metavar="reservation-id",
    )
    subparser.set_defaults(func=ClientCommands.wait_reservation)

    subparser = subparsers.add_parser("reservations", help="list current reservations")
    subparser.set_defaults(func=ClientCommands.print_reservations)

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
    subparser.set_defaults(func=ClientCommands.export)

    subparser = subparsers.add_parser("version", help="show version")
    subparser.set_defaults(func=ClientCommands.print_version)

    adb_subparser = subparsers.add_parser("adb", help="Run Android Debug Bridge")
    adb_subparser.add_argument("--name", "-n", help="optional resource name")
    adb_subparser.add_argument(
        "adb_args", nargs=argparse.REMAINDER, help="adb command to execute (e.g. 'shell', 'devices', etc.)"
    )
    adb_subparser.set_defaults(func=ClientCommands.adb)

    adb_subparsers = adb_subparser.add_subparsers(dest="adb_command")
    scrcpy_subparser = adb_subparsers.add_parser("scrcpy", help="Run scrcpy to remote control an android device")
    scrcpy_subparser.add_argument("--name", "-n", help="optional resource name")
    scrcpy_subparser.set_defaults(func=ClientCommands.scrcpy)

    return parser


def main():
    import inspect

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

    parser = get_parser()

    # make any leftover arguments available for some commands
    args, leftover = parser.parse_known_args()
    if args.command not in ["ssh", "rsync", "forward", "adb", "scrcpy"]:
        args = parser.parse_args()
    else:
        args.leftover = leftover

    # handle dynamic defaults
    if args.config is None:
        args.config = os.environ.get("LG_ENV")

    if args.place is None:
        args.place = place

    if args.state is None:
        args.state = state

    if args.initial_state is None:
        args.initial_state = initial_state

    if args.command in ["cancel-reservation", "wait"] and args.reservation_id is None:
        reservation_id = _get_reservation_id_from_env()
        if reservation_id:
            args.reservation_id = reservation_id
        else:
            print("Please provide a reservation id (previously called token)", file=sys.stderr)
            exit(1)

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

            tls = args.tls
            cacert = args.cacert
            if env:
                tls = env.config.get_option("coordinator_tls", tls)
                if isinstance(tls, str):
                    tls = tls.strip().lower() == "true"
                else:
                    tls = tls is True

                if not cacert:
                    cacert = env.config.get_option("coordinator_cacert", "")
                    if cacert:
                        cacert = env.config.resolve_path(str(cacert))

            logging.debug('Starting session with "%s"', coordinator_address)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            session = start_session(
                coordinator_address,
                extra=extra,
                credentials=get_client_credentials(tls, cacert),
                debug=args.debug,
                loop=loop,
            )
            logging.debug("Started session")
            commands = ClientCommands(session, args, parser.prog)

            try:
                if inspect.iscoroutinefunction(args.func):
                    if getattr(args.func, "needs_target", False):
                        place = commands.get_acquired_place()
                        target = commands._get_target(place)
                        coro = args.func(commands, place, target)
                    else:
                        coro = args.func(commands)
                    session.loop.run_until_complete(coro)
                else:
                    args.func(commands)
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
        except (Error, ErrorGroup) as e:
            if args.debug:
                traceback.print_exc(file=sys.stderr)
            else:
                print(f"{parser.prog}: {e}", file=sys.stderr)
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
