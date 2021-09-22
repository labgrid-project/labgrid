"""The remote.client module contains the functionality to connect to a
coordinator, acquire a place and interact with the connected resources"""
import argparse
import asyncio
import contextlib
import os
import subprocess
import traceback
import logging
import signal
import sys
from textwrap import indent
from socket import gethostname
from getpass import getuser
from collections import defaultdict, OrderedDict
from datetime import datetime
from pprint import pformat
import txaio
from autobahn.asyncio.wamp import ApplicationSession

from .common import *
from ..environment import Environment
from ..exceptions import NoDriverFoundError, NoResourceFoundError, InvalidConfigError
from ..resource.remote import RemotePlaceManager, RemotePlace
from ..util.dict import diff_dict, flat_dict, filter_dict
from ..util.yaml import dump
from .. import Target, target_factory
from ..util.proxy import proxymanager
from ..util.helper import processwrapper
from ..driver import Mode

txaio.use_asyncio()
txaio.config.loop = asyncio.get_event_loop()


class Error(Exception):
    pass


class UserError(Error):
    pass


class ServerError(Error):
    pass


class ClientSession(ApplicationSession):
    """The ClientSession encapsulates all the actions a Client can Invoke on
    the coordinator."""

    def gethostname(self):
        return os.environ.get('LG_HOSTNAME', gethostname())

    def getuser(self):
        return os.environ.get('LG_USERNAME', getuser())

    def onConnect(self):
        """Actions which are executed if a connection is successfully opened."""
        self.loop = self.config.extra['loop']
        self.connected = self.config.extra['connected']
        self.args = self.config.extra.get('args')
        self.env = self.config.extra.get('env', None)
        self.role = self.config.extra.get('role', None)
        self.prog = self.config.extra.get('prog', os.path.basename(sys.argv[0]))
        self.monitor = self.config.extra.get('monitor', False)
        enable_tcp_nodelay(self)
        self.join(
            self.config.realm, authmethods=["ticket"],
            authid=f"client/{self.gethostname()}/{self.getuser()}"
        )

    def onChallenge(self, challenge):
        return "dummy-ticket"

    async def onJoin(self, details):
        # FIXME race condition?
        resources = await self.call(
            'org.labgrid.coordinator.get_resources'
        )
        self.resources = {}
        for exporter, groups in resources.items():
            for group_name, group in sorted(groups.items()):
                for resource_name, resource in sorted(group.items()):
                    await self.on_resource_changed(
                        exporter, group_name, resource_name, resource
                    )

        places = await self.call('org.labgrid.coordinator.get_places')
        self.places = {}
        for placename, config in places.items():
            await self.on_place_changed(placename, config)

        await self.subscribe(
            self.on_resource_changed,
            'org.labgrid.coordinator.resource_changed'
        )
        await self.subscribe(
            self.on_place_changed, 'org.labgrid.coordinator.place_changed'
        )
        await self.connected(self)

    async def on_resource_changed(self, exporter, group_name, resource_name, resource):
        group = self.resources.setdefault(exporter,
                                          {}).setdefault(group_name, {})
        # Do not replace the ResourceEntry object, as other components may keep
        # a reference to it and want to see changes.
        if resource_name not in group:
            old = None
            group[resource_name] = ResourceEntry(resource)
        else:
            old = group[resource_name].data
            group[resource_name].data = resource
        if self.monitor:
            if resource and not old:
                print(f"Resource {exporter}/{group_name}/{resource_name} created: {resource}")
            elif resource and old:
                print(f"Resource {exporter}/{group_name}/{resource_name} changed:")
                for k, v_old, v_new in diff_dict(flat_dict(old), flat_dict(resource)):
                    print(f"  {k}: {v_old} -> {v_new}")
            else:
                print(f"Resource {exporter}/{group_name}/{resource_name} deleted")

    async def on_place_changed(self, name, config):
        if not config:
            del self.places[name]
            if self.monitor:
                print(f"Place {name} deleted")
            return
        config = config.copy()
        config['name'] = name
        config['matches'] = [ResourceMatch(**match) \
            for match in config['matches']]
        config = filter_dict(config, Place, warn=True)
        if name not in self.places:
            place = Place(**config)
            self.places[name] = place
            if self.monitor:
                print(f"Place {name} created: {place}")
        else:
            place = self.places[name]
            old = flat_dict(place.asdict())
            place.update(config)
            new = flat_dict(place.asdict())
            if self.monitor:
                print(f"Place {name} changed:")
                for k, v_old, v_new in diff_dict(old, new):
                    print(f"  {k}: {v_old} -> {v_new}")

    async def do_monitor(self):
        self.monitor = True
        while True:
            await asyncio.sleep(3600.0)

    async def complete(self):
        if self.args.type == 'resources':
            for exporter, groups in sorted(self.resources.items()):
                for group_name, group in sorted(groups.items()):
                    for _, resource in sorted(group.items()):
                        print(f"{exporter}/{group_name}/{resource.cls}")
        elif self.args.type == 'places':
            for name in sorted(self.places.keys()):
                print(name)

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
                    if match and not match.ismatch((exporter, group_name,
                                                    resource.cls, resource_name)):
                        continue

                    filtered[exporter][group_name][resource_name] = resource

        # print the filtered resources
        if self.args.verbose and not self.args.sort_by_matched_place_change:
            for exporter, groups in sorted(filtered.items()):
                print(f"Exporter '{exporter}':")
                for group_name, group in sorted(groups.items()):
                    print(f"  Group '{group_name}' ({exporter}/{group_name}/*):")
                    for resource_name, resource in sorted(group.items()):
                        print("    Resource '{res}' ({exporter}/{group}/{res_cls}[/{res}]):"
                              .format(res=resource_name, exporter=exporter, group=group_name,
                                      res_cls=resource.cls))
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
                    places_strs = [
                        f"{p.name}: {datetime.fromtimestamp(p.changed):%Y-%m-%d}"
                        for p in places
                    ]
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
        result = [tuple('User Host Place Changed'.split())]
        for name, place in self.places.items():
            if place.acquired is None:
                continue
            host, user = place.acquired.split('/')
            result.append((user, host, name, str(datetime.fromtimestamp(place.changed))))
        result.sort()
        widths = [max(map(len, c)) for c in zip(*result)]
        for user, host, name, changed in result:
            print("{0:<{width[0]}s}  {1:<{width[1]}s}  {2:<{width[2]}s}  {3}".format(
                user, host, name, changed, width=widths))

    def _match_places(self, pattern):
        """search for substring matches of pattern in place names and aliases

        Aliases in the format "namespace:alias" only match if the namespace is
        the current user name.
        """
        result = set()

        # reservation token lookup
        token = None
        if pattern.startswith('+'):
            token = pattern[1:]
            if not token:
                token = os.environ.get('LG_TOKEN', None)
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
                if ':' in alias:
                    namespace, alias = alias.split(':', 1)
                    if namespace != self.getuser():
                        continue
                    elif alias == pattern:  # prefer user namespace
                        return [name]
                if pattern in alias:
                    result.add(name)
        return list(result)

    def _check_allowed(self, place):
        if not place.acquired:
            raise UserError(f"place {place.name} is not acquired")
        if self.gethostname()+'/'+self.getuser() not in place.allowed:
            host, user = place.acquired.split('/')
            if user != self.getuser():
                raise UserError(
                    f"place {place.name} is not acquired by your user, acquired by {user}"
                )
            if host != self.gethostname():
                raise UserError(
                    f"place {place.name} is not acquired on this computer, acquired on {host}"
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
            raise UserError(
                f"pattern {pattern} matches multiple places ({', '.join(places)})"
            )
        return self.places[places[0]]

    def get_idle_place(self, place=None):
        place = self.get_place(place)
        if place.acquired:
            raise UserError(f"place {place.name} is not idle (acquired by {place.acquired})")
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
                resource = self.resources[exporter][group_name][resource_name]
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
            raise UserError("missing place name. Set with -p <place> or via env var $PLACE")
        if name in self.places:
            raise UserError(f"{name} already exists")
        res = await self.call('org.labgrid.coordinator.add_place', name)
        if not res:
            raise ServerError(f"failed to add place {name}")
        return res

    async def del_place(self):
        """Delete a place from the coordinator"""
        pattern = self.args.place
        if pattern not in self.places:
            raise UserError("deletes require an exact place name")
        place = self.places[pattern]
        if place.acquired:
            raise UserError(f"place {place.name} is not idle (acquired by {place.acquired})")
        name = place.name
        if not name:
            raise UserError("missing place name. Set with -p <place> or via env var $PLACE")
        if name not in self.places:
            raise UserError(f"{name} does not exist")
        res = await self.call('org.labgrid.coordinator.del_place', name)
        if not res:
            raise ServerError(f"failed to delete place {name}")
        return res

    async def add_alias(self):
        """Add an alias for a place on the coordinator"""
        place = self.get_idle_place()
        alias = self.args.alias
        if alias in place.aliases:
            raise UserError(
                f"place {place.name} already has alias {alias}"
            )
        res = await self.call(
            'org.labgrid.coordinator.add_place_alias', place.name, alias
        )
        if not res:
            raise ServerError(
                f"failed to add alias {alias} for place {place.name}"
            )
        return res

    async def del_alias(self):
        """Delete an alias for a place from the coordinator"""
        place = self.get_idle_place()
        alias = self.args.alias
        if alias not in place.aliases:
            raise UserError(f"place {place.name} has no alias {alias}")
        res = await self.call(
            'org.labgrid.coordinator.del_place_alias', place.name, alias
        )
        if not res:
            raise ServerError(
                f"failed to delete alias {alias} for place {place.name}"
            )
        return res

    async def set_comment(self):
        """Set the comment on a place"""
        place = self.get_place()
        comment = ' '.join(self.args.comment)
        res = await self.call(
            'org.labgrid.coordinator.set_place_comment', place.name, comment
        )
        if not res:
            raise ServerError(
                f"failed to set comment {comment} for place {place.name}"
            )
        return res

    async def set_tags(self):
        """Set the tags on a place"""
        place = self.get_place()
        tags = {}
        for pair in self.args.tags:
            try:
                k, v = pair.split('=')
            except ValueError:
                raise UserError(f"tag '{pair}' needs to match '<key>=<value>'")
            if not TAG_KEY.match(k):
                raise UserError(
                    f"tag key '{k}' needs to match the rexex '{TAG_KEY.pattern}'"
                )
            if not TAG_VAL.match(v):
                raise UserError(
                    f"tag value '{v}' needs to match the rexex '{TAG_VAL.pattern}'"
                )
            tags[k] = v
        res = await self.call(
            'org.labgrid.coordinator.set_place_tags', place.name, tags
        )
        if not res:
            raise ServerError(
                f"failed to set tags {' '.join(self.args.tags)} for place {place.name}"
            )
        return res

    async def add_match(self):
        """Add a match for a place, making fuzzy matching available to the
        client"""
        place = self.get_idle_place()
        if place.acquired:
            raise UserError(f"can not change acquired place {place.name}")
        for pattern in self.args.patterns:
            if pattern in map(repr, place.matches):
                print(f"pattern '{pattern}' exists, skipping")
                continue
            if not 2 <= pattern.count("/") <= 3:
                raise UserError(
                    f"invalid pattern format '{pattern}' (use 'exporter/group/cls/name')"
                )
            res = await self.call(
                'org.labgrid.coordinator.add_place_match', place.name, pattern
            )
            if not res:
                raise ServerError(
                    f"failed to add match {pattern} for place {place.name}"
                )

    async def del_match(self):
        """Delete a match for a place"""
        place = self.get_idle_place()
        if place.acquired:
            raise UserError(f"can not change acquired place {place.name}")
        for pattern in self.args.patterns:
            if pattern not in map(repr, place.matches):
                print(f"pattern '{pattern}' not found, skipping")
                continue
            if not 2 <= pattern.count("/") <= 3:
                raise UserError(
                    f"invalid pattern format '{pattern}' (use 'exporter/group/cls/name')"
                )
            res = await self.call(
                'org.labgrid.coordinator.del_place_match', place.name, pattern
            )
            if not res:
                raise ServerError(
                    f"failed to delete match {pattern} for place {place.name}"
                )

    async def add_named_match(self):
        """Add a named match for a place.

        Fuzzy matching is not allowed to avoid accidental names conflicts."""
        place = self.get_idle_place()
        if place.acquired:
            raise UserError(f"can not change acquired place {place.name}")
        pattern = self.args.pattern
        name = self.args.name
        if pattern in map(repr, place.matches):
            raise UserError(f"pattern '{pattern}' exists")
        if not 2 <= pattern.count("/") <= 3:
            raise UserError(
                f"invalid pattern format '{pattern}' (use 'exporter/group/cls/name')"
            )
        if '*' in pattern:
            raise UserError(
                f"invalid pattern '{pattern}' ('*' not allowed for named matches)"
            )
        if not name:
            raise UserError(
                f"invalid name '{name}'"
            )
        res = await self.call(
            'org.labgrid.coordinator.add_place_match', place.name, pattern, name
        )
        if not res:
            raise ServerError(
                f"failed to add match {pattern} for place {place.name}"
            )

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
        place = self.get_place()
        if place.acquired:
            raise UserError(
                f"place {place.name} is already acquired by {place.acquired}"
            )

        if not self.args.allow_unmatched:
            self.check_matches(place)

        res = await self.call(
            'org.labgrid.coordinator.acquire_place', place.name
        )

        if res:
            print(f"acquired place {place.name}")
            return

        # check potential failure causes
        for exporter, groups in sorted(self.resources.items()):
            for group_name, group in sorted(groups.items()):
                for resource_name, resource in sorted(group.items()):
                    resource_path = (exporter, group_name, resource.cls, resource_name)
                    if resource.acquired is None:
                        continue
                    match = place.getmatch(resource_path)
                    if match is None:
                        continue
                    name = resource_name
                    if match.rename:
                        name = match.rename
                    print(f"Matching resource '{name}' ({exporter}/{group_name}/{resource.cls}/{resource_name}) already acquired by place '{resource.acquired}'")  # pylint: disable=line-too-long

        raise ServerError(f"failed to acquire place {place.name}")

    async def release(self):
        """Release a previously acquired place"""
        place = self.get_place()
        if not place.acquired:
            raise UserError(f"place {place.name} is not acquired")
        _, user = place.acquired.split('/')
        if user != self.getuser():
            if not self.args.kick:
                raise UserError(f"place {place.name} is acquired by a different user ({place.acquired}), use --kick if you are sure")  # pylint: disable=line-too-long
            print(f"warning: kicking user ({place.acquired})")
        res = await self.call(
            'org.labgrid.coordinator.release_place', place.name
        )
        if not res:
            raise ServerError(f"failed to release place {place.name}")

        print(f"released place {place.name}")

    async def allow(self):
        """Allow another use access to a previously acquired place"""
        place = self.get_place()
        if not place.acquired:
            raise UserError(f"place {place.name} is not acquired")
        _, user = place.acquired.split('/')
        if user != self.getuser():
            raise UserError(
                f"place {place.name} is acquired by a different user ({place.acquired})"
            )
        if not '/' in self.args.user:
            raise UserError(
                f"user {self.args.user} must be in <host>/<username> format"
            )
        res = await self.call('org.labgrid.coordinator.allow_place', place.name, self.args.user)
        if not res:
            raise ServerError(f"failed to allow {self.args.user} for place {place.name}")

        print(f"allowed {self.args.user} for place {place.name}")

    def get_target_resources(self, place):
        self._check_allowed(place)
        resources = {}
        for resource_path in place.acquired_resources:
            match = place.getmatch(resource_path)
            (exporter, group_name, _, resource_name) = resource_path
            name = resource_name
            if match.rename:
                name = match.rename
            resources[name] = self.resources[exporter][group_name][resource_name]
        return resources

    def get_target_config(self, place):
        config = {}
        resources = config['resources'] = []
        for name, resource in self.get_target_resources(place).items():
            args = OrderedDict()
            if name != resource.cls:
                args['name'] = name
            args.update(resource.args)
            resources.append({resource.cls: args})
        return config

    def print_env(self):
        place = self.get_acquired_place()
        env = {'targets': {place.name: self.get_target_config(place)}}
        print(dump(env))

    def _prepare_manager(self):
        manager = RemotePlaceManager.get()
        manager.session = self
        manager.loop = self.loop

    def _get_target(self, place):
        self._prepare_manager()
        target = None
        if self.env:
            target = self.env.get_target(self.role)
        if target:
            if self.args.state:
                if self.args.verbose >= 2:
                    from labgrid.stepreporter import StepReporter
                    StepReporter()
                from labgrid.strategy import Strategy
                from labgrid.driver import SerialDriver
                strategy = target.get_driver(Strategy)
                print(f"Transitioning into state {self.args.state}")
                strategy.transition(self.args.state)
                serial = target.get_active_driver(SerialDriver)
                target.deactivate(serial)
        else:
            target = Target(place.name, env=self.env)
            RemotePlace(target, name=place.name)
        return target

    def power(self):
        place = self.get_acquired_place()
        action = self.args.action
        delay = self.args.delay
        target = self._get_target(place)
        from ..driver.powerdriver import (NetworkPowerDriver, PDUDaemonDriver,
                                          USBPowerDriver, SiSPMPowerDriver)
        from ..driver.mqtt import TasmotaPowerDriver
        from ..resource.power import NetworkPowerPort, PDUDaemonPort
        from ..resource.remote import (NetworkUSBPowerPort, NetworkSiSPMPowerPort)
        from ..resource.mqtt import TasmotaPowerPort

        drv = None
        try:
            drv = target.get_driver("PowerProtocol")
        except NoDriverFoundError:
            for resource in target.resources:
                if isinstance(resource, NetworkPowerPort):
                    try:
                        drv = target.get_driver(NetworkPowerDriver)
                    except NoDriverFoundError:
                        drv = NetworkPowerDriver(target, name=None)
                elif isinstance(resource, NetworkUSBPowerPort):
                    try:
                        drv = target.get_driver(USBPowerDriver)
                    except NoDriverFoundError:
                        drv = USBPowerDriver(target, name=None)
                elif isinstance(resource, NetworkSiSPMPowerPort):
                    try:
                        drv = target.get_driver(SiSPMPowerDriver)
                    except NoDriverFoundError:
                        drv = SiSPMPowerDriver(target, name=None)
                elif isinstance(resource, PDUDaemonPort):
                    try:
                        drv = target.get_driver(PDUDaemonDriver)
                    except NoDriverFoundError:
                        drv = PDUDaemonDriver(target, name=None)
                elif isinstance(resource, TasmotaPowerPort):
                    try:
                        drv = target.get_driver(TasmotaPowerDriver)
                    except NoDriverFoundError:
                        drv = TasmotaPowerDriver(target, name=None)
                if drv:
                    break

        if not drv:
            raise UserError("target has no compatible resource available")
        if delay is not None:
            drv.delay = delay
        target.activate(drv)
        res = getattr(drv, action)()
        if action == 'get':
            print(
                f"power for place {place.name} is {'on' if res else 'off'}"
            )

    def digital_io(self):
        place = self.get_acquired_place()
        action = self.args.action
        name = self.args.name
        target = self._get_target(place)
        from ..resource.modbus import ModbusTCPCoil
        from ..resource.onewireport import OneWirePIO
        from ..resource.remote import NetworkDeditecRelais8
        from ..resource.remote import NetworkSysfsGPIO
        from ..resource.remote import NetworkLXAIOBusPIO
        from ..resource.remote import NetworkHIDRelay
        from ..driver.modbusdriver import ModbusCoilDriver
        from ..driver.onewiredriver import OneWirePIODriver
        from ..driver.deditecrelaisdriver import DeditecRelaisDriver
        from ..driver.gpiodriver import GpioDigitalOutputDriver
        from ..driver.lxaiobusdriver import LXAIOBusPIODriver
        from ..driver.usbhidrelay import HIDRelayDriver

        drv = None
        try:
            drv = target.get_driver("DigitalOutputProtocol")
        except NoDriverFoundError:
            for resource in target.resources:
                if isinstance(resource, ModbusTCPCoil):
                    try:
                        drv = target.get_driver(ModbusCoilDriver, name=name)
                    except NoDriverFoundError:
                        target.set_binding_map({"coil": name})
                        drv = ModbusCoilDriver(target, name=name)
                elif isinstance(resource, OneWirePIO):
                    try:
                        drv = target.get_driver(OneWirePIODriver, name=name)
                    except NoDriverFoundError:
                        target.set_binding_map({"port": name})
                        drv = OneWirePIODriver(target, name=name)
                elif isinstance(resource, NetworkDeditecRelais8):
                    try:
                        drv = target.get_driver(DeditecRelaisDriver, name=name)
                    except NoDriverFoundError:
                        target.set_binding_map({"relais": name})
                        drv = DeditecRelaisDriver(target, name=name)
                elif isinstance(resource, NetworkSysfsGPIO):
                    try:
                        drv = target.get_driver(GpioDigitalOutputDriver, name=name)
                    except NoDriverFoundError:
                        target.set_binding_map({"gpio": name})
                        drv = GpioDigitalOutputDriver(target, name=name)
                elif isinstance(resource, NetworkLXAIOBusPIO):
                    try:
                        drv = target.get_driver(LXAIOBusPIODriver, name=name)
                    except NoDriverFoundError:
                        target.set_binding_map({"pio": name})
                        drv = LXAIOBusPIODriver(target, name=name)
                elif isinstance(resource, NetworkHIDRelay):
                    try:
                        drv = target.get_driver(HIDRelayDriver, name=name)
                    except NoDriverFoundError:
                        target.set_binding_map({"relay": name})
                        drv = HIDRelayDriver(target, name=name)
                if drv:
                    break

        if not drv:
            raise UserError("target has no compatible resource available")
        target.activate(drv)
        if action == 'get':
            print(f"digital IO {name} for place {place.name} is {'high' if drv.get() else 'low'}")
        elif action == 'high':
            drv.set(True)
        elif action == 'low':
            drv.set(False)

    async def _console(self, place, target, *, logfile=None):
        name = self.args.name
        from ..resource import NetworkSerialPort
        resource = target.get_resource(NetworkSerialPort, name=name)
        host, port = proxymanager.get_host_and_port(resource)

        # check for valid resources
        assert port is not None, "Port is not set"

        call = [
            'microcom', '-s', str(resource.speed), '-t',
            f"{host}:{port}"
        ]
        if logfile:
            call.append(f"--logfile={logfile}")
        print(f"connecting to {resource} calling {' '.join(call)}")
        try:
            p = await asyncio.create_subprocess_exec(*call)
        except FileNotFoundError as e:
            raise ServerError(f"failed to execute microcom: {e}")
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
            print("connection lost")
            return False
        return True

    async def console(self, place, target):
        while True:
            res = await self._console(place, target, logfile=self.args.logfile)
            if res:
                break
            if not self.args.loop:
                break
            await asyncio.sleep(1.0)
    console.needs_target = True

    def fastboot(self):
        place = self.get_acquired_place()
        args = self.args.fastboot_args
        if not args:
            raise UserError("not enough arguments for fastboot")
        if args[0] == 'flash':
            if len(args) < 3:
                raise UserError("not enough arguments for fastboot flash")
            args[2] = os.path.abspath(args[2])
        elif args[0] == 'boot':
            if len(args) < 2:
                raise UserError("not enough arguments for fastboot boot")
            args[1:] = map(os.path.abspath, args[1:])
        target = self._get_target(place)
        from ..driver.fastbootdriver import AndroidFastbootDriver
        try:
            drv = target.get_driver(AndroidFastbootDriver)
        except NoDriverFoundError:
            drv = AndroidFastbootDriver(target, name=None)
        drv.fastboot.timeout = self.args.wait
        target.activate(drv)
        if args[0] == 'flash':
            drv.flash(args[1], args[2])
            return
        if args[0] == 'boot':
            drv.boot(args[1])
            return
        if args[0:2] == ['oem', 'exec']:
            drv.run(" ".join(args[2:]))
            return
        drv(*args)

    def flashscript(self):
        place = self.get_acquired_place()
        target = self._get_target(place)
        from ..driver.flashscriptdriver import FlashScriptDriver
        from ..resource.remote import NetworkUSBFlashableDevice

        drv = None
        try:
            drv = target.get_driver(FlashScriptDriver)
        except NoDriverFoundError:
            for resource in target.resources:
                if isinstance(resource, NetworkUSBFlashableDevice):
                    drv = FlashScriptDriver(target, name=None)
                    break
        if not drv:
            raise UserError("target has no compatible resource available")
        target.activate(drv)
        drv.flash(script=self.args.script, args=self.args.script_args)

    def bootstrap(self):
        place = self.get_acquired_place()
        args = self.args.filename
        target = self._get_target(place)
        from ..protocol.bootstrapprotocol import BootstrapProtocol
        from ..driver.usbloader import IMXUSBDriver, MXSUSBDriver, RKUSBDriver
        from ..driver.openocddriver import OpenOCDDriver
        from ..resource.remote import (NetworkMXSUSBLoader, NetworkIMXUSBLoader, NetworkRKUSBLoader,
                                       NetworkAlteraUSBBlaster)
        drv = None
        try:
            drv = target.get_driver(BootstrapProtocol)
        except NoDriverFoundError:
            for resource in target.resources:
                if isinstance(resource, NetworkIMXUSBLoader):
                    try:
                        drv = target.get_driver(IMXUSBDriver)
                    except NoDriverFoundError:
                        drv = IMXUSBDriver(target, name=None)
                    drv.loader.timeout = self.args.wait
                elif isinstance(resource, NetworkMXSUSBLoader):
                    try:
                        drv = target.get_driver(MXSUSBDriver)
                    except NoDriverFoundError:
                        drv = MXSUSBDriver(target, name=None)
                    drv.loader.timeout = self.args.wait
                elif isinstance(resource, NetworkAlteraUSBBlaster):
                    args = dict(arg.split('=', 1) for arg in self.args.bootstrap_args)
                    try:
                        drv = target.get_driver(OpenOCDDriver)
                    except NoDriverFoundError:
                        drv = OpenOCDDriver(target, name=None, **args)
                    drv.interface.timeout = self.args.wait
                elif isinstance(resource, NetworkRKUSBLoader):
                    try:
                        drv = target.get_driver(RKUSBDriver)
                    except NoDriverFoundError:
                        drv = RKUSBDriver(target, name=None)
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
        from ..driver.usbsdmuxdriver import USBSDMuxDriver
        from ..driver.usbsdwiredriver import USBSDWireDriver
        from ..resource.remote import NetworkUSBSDMuxDevice, NetworkUSBSDWireDevice

        drv = None
        for resource in target.resources:
            if isinstance(resource, NetworkUSBSDMuxDevice):
                try:
                    drv = target.get_driver(USBSDMuxDriver)
                except NoDriverFoundError:
                    drv = USBSDMuxDriver(target, name=None)
            elif isinstance(resource, NetworkUSBSDWireDevice):
                try:
                    drv = target.get_driver(USBSDWireDriver)
                except NoDriverFoundError:
                    drv = USBSDWireDriver(target, name=None)
            if drv:
                break

        if not drv:
            raise UserError("target has no compatible resource available")
        target.activate(drv)
        if isinstance(drv, USBSDWireDriver) and action in ['off', 'client', 'get']:
            raise UserError("sd-wire does only supports setting 'dut' and 'host' modes")

        if action == 'get':
            print(drv.get_mode())
        else:
            drv.set_mode(action)

    def usb_mux(self):
        place = self.get_acquired_place()
        links = self.args.links
        if links == 'off':
            links = []
        elif links == 'host-dut+host-device':
            links = ['host-dut', 'host-device']
        else:
            links = [links]
        target = self._get_target(place)
        from ..driver.lxausbmuxdriver import LXAUSBMuxDriver
        from ..resource.remote import NetworkLXAUSBMux

        drv = None
        for resource in target.resources:
            if isinstance(resource, NetworkLXAUSBMux):
                try:
                    drv = target.get_driver(LXAUSBMuxDriver)
                except NoDriverFoundError:
                    drv = LXAUSBMuxDriver(target, name=None)
                break

        if not drv:
            raise UserError("target has no compatible resource available")
        target.activate(drv)
        drv.set_links(links)

    def _get_ip(self, place):
        target = self._get_target(place)
        from ..resource import EthernetPort, NetworkService
        try:
            resource = target.get_resource(EthernetPort)
        except NoResourceFoundError:
            resource = target.get_resource(NetworkService)
            return resource.address

        matches = []
        for details in resource.extra.get('macs').values():
            ips = details.get('ips', [])
            if not ips:
                continue
            matches.append((details['timestamp'], ips))
        matches.sort()
        newest = matches[-1][1]
        if len(ips) > 1:
            print(f"multiple IPs found: {ips}")
            return None
        return newest[0]

    def _get_ssh(self):
        place = self.get_acquired_place()
        target = self._get_target(place)

        from ..resource import NetworkService
        try:
            target.get_resource(NetworkService)
        except NoResourceFoundError:
            ip = self._get_ip(place)
            if not ip:
                return
            NetworkService(target, address=str(ip), username='root')

        from ..driver.sshdriver import SSHDriver
        try:
            drv = target.get_driver(SSHDriver)
        except NoDriverFoundError:
            drv = SSHDriver(target, name=None)
        target.activate(drv)
        return drv

    def ssh(self):
        drv = self._get_ssh()

        res = drv.interact(self.args.leftover)
        if res == 255:
            print("connection lost (SSH error)")
        elif res:
            print(f"connection lost (remote exit code {res})")

    def scp(self):
        drv = self._get_ssh()

        res = drv.scp(src=self.args.src, dst=self.args.dst)

    def rsync(self):
        drv = self._get_ssh()

        res = drv.rsync(src=self.args.src, dst=self.args.dst, extra=self.args.leftover)

    def sshfs(self):
        drv = self._get_ssh()

        res = drv.sshfs(path=self.args.path, mountpoint=self.args.mountpoint)

    def forward(self):
        if not self.args.local and not self.args.remote:
            print("Nothing to forward")
            return

        drv = self._get_ssh()

        with contextlib.ExitStack() as stack:
            for local, remote in self.args.local:
                localport = stack.enter_context(drv.forward_local_port(remote, localport=local))
                print(f"Forwarding local port {localport:d} to remote port {remote:d}")

            for local, remote in self.args.remote:
                stack.enter_context(drv.forward_remote_port(remote, localport))
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
        args = ['telnet', str(ip)]
        res = subprocess.call(args)
        if res:
            print("connection lost")

    def video(self):
        place = self.get_acquired_place()
        quality = self.args.quality
        controls = self.args.controls
        target = self._get_target(place)
        from ..driver.usbvideodriver import USBVideoDriver
        from ..driver.httpvideodriver import HTTPVideoDriver
        from ..resource.httpvideostream import HTTPVideoStream
        from ..resource.udev import USBVideo
        from ..resource.remote import NetworkUSBVideo
        drv = None
        try:
            drv = target.get_driver("VideoProtocol")
        except NoDriverFoundError:
            for resource in target.resources:
                if isinstance(resource, (USBVideo, NetworkUSBVideo)):
                    try:
                        drv = target.get_driver(USBVideoDriver)
                    except NoDriverFoundError:
                        drv = USBVideoDriver(target, name=None)
                elif isinstance(resource, HTTPVideoStream):
                    try:
                        drv = target.get_driver(HTTPVideoDriver)
                    except NoDriverFoundError:
                        drv = HTTPVideoDriver(target, name=None)
                if drv:
                    break
        if not drv:
            raise UserError("target has no compatible resource available")

        target.activate(drv)
        if quality == 'list':
            default, variants = drv.get_qualities()
            for name, caps in variants:
                mark = '*' if default == name else ' '
                print(f"{mark} {name:<10s} {caps:s}")
        else:
            drv.stream(quality, controls=controls)

    def audio(self):
        place = self.get_acquired_place()
        target = self._get_target(place)
        from ..driver.usbaudiodriver import USBAudioInputDriver
        drv = None
        try:
            drv = target.get_driver(USBAudioInputDriver)
        except NoDriverFoundError:
            drv = USBAudioInputDriver(target, name=None)
        target.activate(drv)
        drv.play()

    def _get_tmc(self):
        place = self.get_acquired_place()
        target = self._get_target(place)
        from ..driver.usbtmcdriver import USBTMCDriver
        from ..resource.remote import NetworkUSBTMC
        drv = None
        for resource in target.resources:
            if isinstance(resource, NetworkUSBTMC):
                try:
                    drv = target.get_driver(USBTMCDriver)
                except NoDriverFoundError:
                    drv = USBTMCDriver(target, name=None)
                break
        if not drv:
            raise UserError("target has no compatible resource available")
        target.activate(drv)
        return drv

    def tmc_command(self):
        drv = self._get_tmc()
        command = ' '.join(self.args.command)
        if not command:
            raise UserError("no command given")
        if '?' in command:
            result = drv.query(command)
            print(result)
        else:
            drv.command(command)

    def tmc_query(self):
        drv = self._get_tmc()
        query = ' '.join(self.args.query)
        if not query:
            raise UserError("no query given")
        result = drv.query(query)
        print(result)

    def tmc_screen(self):
        drv = self._get_tmc()
        action = self.args.action
        if action in ['show', 'save']:
            extension, data = drv.get_screenshot()
            filename = 'tmc-screen_{0:%Y-%m-%d}_{0:%H:%M:%S}.{1}'.format(datetime.now(), extension)
            open(filename, 'wb').write(data)
            print(f"Saved as {filename}")
            if action == 'show':
                subprocess.call(['xdg-open', filename])

    def tmc_channel(self):
        drv = self._get_tmc()
        channel = self.args.channel
        action = self.args.action
        if action == 'info':
            data = drv.get_channel_info(channel)
        elif action == 'values':
            data = drv.get_channel_values(channel)
        for k, v in sorted(data.items()):
            print(f"{k:<16s} {str(v):<10s}")

    def write_image(self):
        place = self.get_acquired_place()
        target = self._get_target(place)
        drv = None
        from ..resource.remote import NetworkUSBMassStorage, NetworkUSBSDMuxDevice, \
            NetworkUSBSDWireDevice
        from ..driver import USBStorageDriver
        try:
            drv = target.get_driver(USBStorageDriver)
        except NoDriverFoundError:
            for resource in target.resources:
                if isinstance(resource, (NetworkUSBSDMuxDevice, NetworkUSBSDWireDevice,
                                         NetworkUSBMassStorage)):
                    try:
                        drv = target.get_driver(USBStorageDriver)
                    except NoDriverFoundError:
                        drv = USBStorageDriver(target, name=None)
                    drv.storage.timeout = self.args.wait
                    break
        if not drv:
            raise UserError("target has no compatible resource available")
        target.activate(drv)
        try:
            drv.write_image(self.args.filename, partition=self.args.partition, skip=self.args.skip,
                            seek=self.args.seek, mode=self.args.write_mode)
        except subprocess.CalledProcessError as e:
            raise UserError(f"could not write image to network usb storage: {e}")
        except FileNotFoundError as e:
            raise UserError(e)

    async def create_reservation(self):
        filters = ' '.join(self.args.filters)
        prio = self.args.prio
        res = await self.call('org.labgrid.coordinator.create_reservation', filters, prio=prio)
        if res is None:
            raise ServerError("failed to create reservation")
        ((token, config),) = res.items() # we get a one-item dict
        config = filter_dict(config, Reservation, warn=True)
        res = Reservation(token=token, **config)
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
        token = self.args.token
        res = await self.call('org.labgrid.coordinator.cancel_reservation', token)
        if not res:
            raise ServerError(f"failed to cancel reservation {token}")

    async def _wait_reservation(self, token, verbose=True):
        while True:
            config = await self.call('org.labgrid.coordinator.poll_reservation', token)
            if config is None:
                raise ServerError("reservation not found")
            config = filter_dict(config, Reservation, warn=True)
            res = Reservation(token=token, **config)
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
        reservations = await self.call('org.labgrid.coordinator.get_reservations')
        for token, config in sorted(reservations.items(), key=lambda x: (-x[1]['prio'], x[1]['created'])):  # pylint: disable=line-too-long
            config = filter_dict(config, Reservation, warn=True)
            res = Reservation(token=token, **config)
            print(f"Reservation '{res.token}':")
            res.show(level=1)


def start_session(url, realm, extra):
    from autobahn.asyncio.wamp import ApplicationRunner

    loop = asyncio.get_event_loop()
    ready = asyncio.Event()

    async def connected(session):  # pylint: disable=unused-argument
        ready.set()

    if not extra:
        extra = {}
    extra['loop'] = loop
    extra['connected'] = connected

    session = [None]

    def make(*args, **kwargs):
        nonlocal session
        session[0] = ClientSession(*args, **kwargs)
        return session[0]

    url = proxymanager.get_url(url, default_port=20408)

    runner = ApplicationRunner(url, realm=realm, extra=extra)
    coro = runner.run(make, start_loop=False)

    transport, protocol = loop.run_until_complete(coro)

    # there is no other notification when the WAMP connection setup times out,
    # so we need to wait for one of these protocol futures to resolve
    done, pending = loop.run_until_complete(asyncio.wait(
        {protocol.is_open, protocol.is_closed},
        timeout=30,
        return_when=asyncio.FIRST_COMPLETED))
    if protocol.is_closed in done:
        raise Error("connection closed during setup")
    if protocol.is_open in pending:
        raise Error("connection timed out during setup")

    loop.run_until_complete(ready.wait())
    return session[0]

def find_role_by_place(config, place):
    for role, role_config in config.items():
        resources, _ = target_factory.normalize_config(role_config)
        remote_places = resources.get('RemotePlace', {})
        remote_place = remote_places.get(place)
        if remote_place:
            return role
    return None

def find_any_role_with_place(config):
    for role, role_config in config.items():
        resources, _ = target_factory.normalize_config(role_config)
        remote_places = resources.get('RemotePlace', {})
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

def main():
    processwrapper.enable_logging()
    logging.basicConfig(
        level=logging.WARNING,
        format='%(levelname)7s: %(message)s',
        stream=sys.stderr,
    )

    # Support both legacy variables and properly namespaced ones
    place = os.environ.get('PLACE', None)
    place = os.environ.get('LG_PLACE', place)
    state = os.environ.get('STATE', None)
    state = os.environ.get('LG_STATE', state)
    token = os.environ.get('LG_TOKEN', None)

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-x',
        '--crossbar',
        metavar='URL',
        type=str,
        default=os.environ.get("LG_CROSSBAR", "ws://127.0.0.1:20408/ws"),
        help="crossbar websocket URL (default: %(default)s)"
    )
    parser.add_argument(
        '-c',
        '--config',
        type=str,
        default=os.environ.get("LG_ENV"),
        help="config file"
    )
    parser.add_argument(
        '-p',
        '--place',
        type=str,
        default=place,
        help="place name/alias"
    )
    parser.add_argument(
        '-s',
        '--state',
        type=str,
        default=state,
        help="strategy state to switch into before command"
    )
    parser.add_argument(
        '-d',
        '--debug',
        action='store_true',
        default=False,
        help="enable debug mode (show python tracebacks)"
    )
    parser.add_argument(
        '-v',
        '--verbose',
        action='count',
        default=0
    )
    parser.add_argument(
        '-P',
        '--proxy',
        type=str,
        help="proxy connections via given ssh host"
    )
    subparsers = parser.add_subparsers(
        dest='command',
        title='available subcommands',
        metavar="COMMAND",
    )

    subparser = subparsers.add_parser('help')

    subparser = subparsers.add_parser('complete')
    subparser.add_argument('type', choices=['resources', 'places'])
    subparser.set_defaults(func=ClientSession.complete)

    subparser = subparsers.add_parser('monitor',
                                      help="monitor events from the coordinator")
    subparser.set_defaults(func=ClientSession.do_monitor)

    subparser = subparsers.add_parser('resources', aliases=('r',),
                                      help="list available resources")
    subparser.add_argument('-a', '--acquired', action='store_true')
    subparser.add_argument('-e', '--exporter')
    subparser.add_argument('--sort-by-matched-place-change', action='store_true',
                           help="sort by matched place's changed date (oldest first) and show place and date")  # pylint: disable=line-too-long
    subparser.add_argument('match', nargs='?')
    subparser.set_defaults(func=ClientSession.print_resources)

    subparser = subparsers.add_parser('places', aliases=('p',),
                                      help="list available places")
    subparser.add_argument('-a', '--acquired', action='store_true')
    subparser.add_argument('--sort-last-changed', action='store_true',
                           help='sort by last changed date (oldest first)')
    subparser.set_defaults(func=ClientSession.print_places)

    subparser = subparsers.add_parser('who',
                                      help="list acquired places by user")
    subparser.set_defaults(func=ClientSession.print_who)

    subparser = subparsers.add_parser('show',
                                      help="show a place and related resources")
    subparser.set_defaults(func=ClientSession.print_place)

    subparser = subparsers.add_parser('create', help="add a new place")
    subparser.set_defaults(func=ClientSession.add_place)

    subparser = subparsers.add_parser('delete', help="delete an existing place")
    subparser.set_defaults(func=ClientSession.del_place)

    subparser = subparsers.add_parser('add-alias',
                                      help="add an alias to a place")
    subparser.add_argument('alias')
    subparser.set_defaults(func=ClientSession.add_alias)

    subparser = subparsers.add_parser('del-alias',
                                      help="delete an alias from a place")
    subparser.add_argument('alias')
    subparser.set_defaults(func=ClientSession.del_alias)

    subparser = subparsers.add_parser('set-comment',
                                      help="update the place comment")
    subparser.add_argument('comment', nargs='+')
    subparser.set_defaults(func=ClientSession.set_comment)

    subparser = subparsers.add_parser('set-tags',
                                      help="update the place tags")
    subparser.add_argument('tags', metavar='KEY=VALUE', nargs='+',
                           help="use an empty value for deletion")
    subparser.set_defaults(func=ClientSession.set_tags)

    subparser = subparsers.add_parser('add-match',
                                      help="add one (or multiple) match pattern(s) to a place")
    subparser.add_argument('patterns', metavar='PATTERN', nargs='+')
    subparser.set_defaults(func=ClientSession.add_match)

    subparser = subparsers.add_parser('del-match',
                                      help="delete one (or multiple) match pattern(s) from a place")
    subparser.add_argument('patterns', metavar='PATTERN', nargs='+')
    subparser.set_defaults(func=ClientSession.del_match)

    subparser = subparsers.add_parser('add-named-match',
                                      help="add one match pattern with a name to a place")
    subparser.add_argument('pattern', metavar='PATTERN')
    subparser.add_argument('name', metavar='NAME')
    subparser.set_defaults(func=ClientSession.add_named_match)

    subparser = subparsers.add_parser('acquire',
                                      aliases=('lock',),
                                      help="acquire a place")
    subparser.add_argument('--allow-unmatched', action='store_true',
                           help="allow missing resources for matches when locking the place")
    subparser.set_defaults(func=ClientSession.acquire)

    subparser = subparsers.add_parser('release',
                                      aliases=('unlock',),
                                      help="release a place")
    subparser.add_argument('-k', '--kick', action='store_true',
                           help="release a place even if it is acquired by a different user")
    subparser.set_defaults(func=ClientSession.release)

    subparser = subparsers.add_parser('allow', help="allow another user to access a place")
    subparser.add_argument('user', help="<host>/<username>")
    subparser.set_defaults(func=ClientSession.allow)

    subparser = subparsers.add_parser('env',
                                      help="generate a labgrid environment file for a place")
    subparser.set_defaults(func=ClientSession.print_env)

    subparser = subparsers.add_parser('power',
                                      aliases=('pw',),
                                      help="change (or get) a place's power status")
    subparser.add_argument('action', choices=['on', 'off', 'cycle', 'get'])
    subparser.add_argument('-t', '--delay', type=float, default=None,
                           help='wait time in seconds between off and on during cycle')
    subparser.set_defaults(func=ClientSession.power)

    subparser = subparsers.add_parser('io',
                                      help="change (or get) a digital IO status")
    subparser.add_argument('action', choices=['high', 'low', 'get'], help="action")
    subparser.add_argument('name', help="optional resource name", nargs='?')
    subparser.set_defaults(func=ClientSession.digital_io)

    subparser = subparsers.add_parser('console',
                                      aliases=('con',),
                                      help="connect to the console")
    subparser.add_argument('-l', '--loop', action='store_true',
                           help="keep trying to connect if the console is unavailable")
    subparser.add_argument('name', help="optional resource name", nargs='?')
    subparser.add_argument('--logfile', metavar="FILE", help="Log output to FILE", default=None)
    subparser.set_defaults(func=ClientSession.console)

    subparser = subparsers.add_parser('fastboot',
                                      help="run fastboot")
    subparser.add_argument('fastboot_args', metavar='ARG', nargs=argparse.REMAINDER,
                           help='fastboot arguments')
    subparser.add_argument('--wait', type=float, default=10.0)
    subparser.set_defaults(func=ClientSession.fastboot)

    subparser = subparsers.add_parser('flashscript',
                                     help="run flash script")
    subparser.add_argument('script', help="Flashing script")
    subparser.add_argument('script_args', metavar='ARG', nargs=argparse.REMAINDER,
                           help='script arguments')
    subparser.set_defaults(func=ClientSession.flashscript)

    subparser = subparsers.add_parser('bootstrap',
                                      help="start a bootloader")
    subparser.add_argument('-w', '--wait', type=float, default=10.0)
    subparser.add_argument('filename', help='filename to boot on the target')
    subparser.add_argument('bootstrap_args', metavar='ARG', nargs=argparse.REMAINDER,
                           help='extra bootstrap arguments')
    subparser.set_defaults(func=ClientSession.bootstrap)

    subparser = subparsers.add_parser('sd-mux',
                                      help="switch USB SD Muxer or get current mode")
    subparser.add_argument('action', choices=['dut', 'host', 'off', 'client', 'get'])
    subparser.set_defaults(func=ClientSession.sd_mux)

    subparser = subparsers.add_parser('usb-mux',
                                      help="switch USB Muxer")
    subparser.add_argument('links', choices=['off', 'dut-device', 'host-dut', 'host-device', 'host-dut+host-device'])
    subparser.set_defaults(func=ClientSession.usb_mux)

    subparser = subparsers.add_parser('ssh',
                                      help="connect via ssh (with optional arguments)")
    subparser.set_defaults(func=ClientSession.ssh)

    subparser = subparsers.add_parser('scp',
                                      help="transfer file via scp")
    subparser.add_argument('src', help='source path (use :dir/file for remote side)')
    subparser.add_argument('dst', help='destination path (use :dir/file for remote side)')
    subparser.set_defaults(func=ClientSession.scp)

    subparser = subparsers.add_parser('rsync',
                                      help="transfer files via rsync")
    subparser.add_argument('src', help='source path (use :dir/file for remote side)')
    subparser.add_argument('dst', help='destination path (use :dir/file for remote side)')
    subparser.set_defaults(func=ClientSession.rsync)

    subparser = subparsers.add_parser('sshfs',
                                      help="mount via sshfs (blocking)")
    subparser.add_argument('path', help='remote path on the target')
    subparser.add_argument('mountpoint', help='local path')
    subparser.set_defaults(func=ClientSession.sshfs)

    subparser = subparsers.add_parser('forward',
                                      help="forward local port to remote target")
    subparser.add_argument("--local", "-L", metavar="[LOCAL:]REMOTE",
                           action=LocalPort,
                           help="Forward local port LOCAL to remote port REMOTE. If LOCAL is unspecified, an arbitrary port will be chosen")
    subparser.add_argument("--remote", "-R", metavar="REMOTE:LOCAL",
                           action=RemotePort,
                           help="Forward remote port REMOTE to local port LOCAL")
    subparser.set_defaults(func=ClientSession.forward)

    subparser = subparsers.add_parser('telnet',
                                      help="connect via telnet")
    subparser.set_defaults(func=ClientSession.telnet)

    subparser = subparsers.add_parser('video',
                                      help="start a video stream")
    subparser.add_argument('-q', '--quality', type=str,
                           help="select a video quality (use 'list' to show options)")
    subparser.add_argument('-c', '--controls', type=str,
                           help="configure v4l controls (such as 'focus_auto=0,focus_absolute=40')")
    subparser.set_defaults(func=ClientSession.video)

    subparser = subparsers.add_parser('audio', help="start a audio stream")
    subparser.set_defaults(func=ClientSession.audio)

    subparser = subparsers.add_parser('tmc', help="control a USB TMC device")
    subparser.set_defaults(func=lambda _: subparser.print_help())
    tmc_subparsers = subparser.add_subparsers(
        dest='subcommand',
        title='available subcommands',
        metavar="SUBCOMMAND",
    )

    tmc_subparser = tmc_subparsers.add_parser('cmd',
                                              aliases=('c',),
                                              help="execute raw command")
    tmc_subparser.add_argument('command', nargs='+')
    tmc_subparser.set_defaults(func=ClientSession.tmc_command)

    tmc_subparser = tmc_subparsers.add_parser('query',
                                              aliases=('q',),
                                              help="execute raw query")
    tmc_subparser.add_argument('query', nargs='+')
    tmc_subparser.set_defaults(func=ClientSession.tmc_query)

    tmc_subparser = tmc_subparsers.add_parser('screen', help="show or save a screenshot")
    tmc_subparser.add_argument('action', choices=['show', 'save'])
    tmc_subparser.set_defaults(func=ClientSession.tmc_screen)

    tmc_subparser = tmc_subparsers.add_parser('channel', help="use a channel")
    tmc_subparser.add_argument('channel', type=int)
    tmc_subparser.add_argument('action', choices=['info', 'values'])
    tmc_subparser.set_defaults(func=ClientSession.tmc_channel)

    subparser = subparsers.add_parser('write-image', help="write an image onto mass storage")
    subparser.add_argument('-w', '--wait', type=float, default=10.0)
    subparser.add_argument('-p', '--partition', type=int, help="partition number to write to")
    subparser.add_argument('--skip', type=int, default=0,
                           help="skip n 512-sized blocks at start of input")
    subparser.add_argument('--seek', type=int, default=0,
                           help="skip n 512-sized blocks at start of output")
    subparser.add_argument('--mode', dest='write_mode',
                           type=Mode, choices=Mode, default=Mode.DD,
                           help="Choose tool for writing images (default: %(default)s)")
    subparser.add_argument('filename', help='filename to boot on the target')
    subparser.set_defaults(func=ClientSession.write_image)

    subparser = subparsers.add_parser('reserve', help="create a reservation")
    subparser.add_argument('--wait', action='store_true',
                           help="wait until the reservation is allocated")
    subparser.add_argument('--shell', action='store_true',
                           help="format output as shell variables")
    subparser.add_argument('--prio', type=float, default=0.0,
                           help="priority relative to other reservations (default 0)")
    subparser.add_argument('filters', metavar='KEY=VALUE', nargs='+',
                           help="required tags")
    subparser.set_defaults(func=ClientSession.create_reservation)

    subparser = subparsers.add_parser('cancel-reservation', help="cancel a reservation")
    subparser.add_argument('token', type=str, default=token, nargs='?' if token else None)
    subparser.set_defaults(func=ClientSession.cancel_reservation)

    subparser = subparsers.add_parser('wait', help="wait for a reservation to be allocated")
    subparser.add_argument('token', type=str, default=token, nargs='?' if token else None)
    subparser.set_defaults(func=ClientSession.wait_reservation)

    subparser = subparsers.add_parser('reservations', help="list current reservations")
    subparser.set_defaults(func=ClientSession.print_reservations)

    # make any leftover arguments available for some commands
    args, leftover = parser.parse_known_args()
    if args.command not in ['ssh', 'rsync', 'forward']:
        args = parser.parse_args()
    else:
        args.leftover = leftover


    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)
    if args.debug or args.verbose > 1:
        logging.getLogger().setLevel(logging.DEBUG)

    if not args.config and args.state:
        print("Setting the state requires a configuration file")
        exit(1)

    if args.proxy:
        proxymanager.force_proxy(args.proxy)

    env = None
    if args.config:
        env = Environment(config_file=args.config)

    role = None
    if env and env.config.get_targets():
        if args.place:
            role = find_role_by_place(env.config.get_targets(), args.place)
            if not role:
                print(f"RemotePlace {args.place} not found in configuration file",
                      file=sys.stderr)
                exit(1)
            print(f"Selected role {role} from configuration file")
        else:
            role, args.place = find_any_role_with_place(env.config.get_targets())
            if not role:
                print("No RemotePlace found in configuration file", file=sys.stderr)
                exit(1)
            print(f"Selected role {role} and place {args.place} from configuration file")

    extra = {
        'args': args,
        'env': env,
        'role': role,
        'prog': parser.prog,
    }

    if args.command and args.command != 'help':
        exitcode = 0
        try:
            session = start_session(args.crossbar, os.environ.get("LG_CROSSBAR_REALM", "realm1"),
                                    extra)
            try:
                if asyncio.iscoroutinefunction(args.func):
                    if getattr(args.func, 'needs_target', False):
                        place = session.get_acquired_place()
                        target = session._get_target(place)
                        coro = args.func(session, place, target)
                    else:
                        coro = args.func(session)
                    session.loop.run_until_complete(coro)
                else:
                    args.func(session)
            finally:
                session.loop.close()
        except NoResourceFoundError as e:
            if args.debug:
                traceback.print_exc()
            else:
                print(f"{parser.prog}: error: {e}", file=sys.stderr)
            print("This may be caused by disconnected exporter or wrong match entries.\nYou can use the 'show' command to review all matching resources.", file=sys.stderr)  # pylint: disable=line-too-long
            exitcode = 1
        except NoDriverFoundError as e:
            if args.debug:
                traceback.print_exc()
            else:
                print(f"{parser.prog}: error: {e}", file=sys.stderr)
            print("This is likely caused by an error or missing driver in the environment configuration.", file=sys.stderr)  # pylint: disable=line-too-long
            exitcode = 1
        except InvalidConfigError as e:
            if args.debug:
                traceback.print_exc()
            else:
                print(f"{parser.prog}: error: {e}", file=sys.stderr)
            print("This is likely caused by an error in the environment configuration or invalid\nresource information provided by the coordinator.", file=sys.stderr)  # pylint: disable=line-too-long
            exitcode = 1
        except ConnectionError as e:
            print(f"Could not connect to coordinator: {e}")
            exitcode = 1
        except Error as e:
            if args.debug:
                traceback.print_exc()
            else:
                print(f"{parser.prog}: error: {e}", file=sys.stderr)
            exitcode = 1
        except KeyboardInterrupt:
            exitcode = 0
        except Exception:  # pylint: disable=broad-except
            traceback.print_exc()
            exitcode = 2
        exit(exitcode)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
