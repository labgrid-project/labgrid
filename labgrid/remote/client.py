"""The remote.client module contains the functionality to connect to a
coordinator, acquire a place and interact with the connected resources"""
import argparse
import asyncio
import txaio
import os
import subprocess
import traceback
import logging
import sys
from pprint import pformat
from textwrap import indent
from socket import gethostname
from getpass import getuser
from collections import defaultdict, OrderedDict
from time import sleep
from datetime import datetime

from autobahn.asyncio.wamp import ApplicationSession

from .common import ResourceEntry, ResourceMatch, Place, enable_tcp_nodelay
from ..environment import Environment
from ..exceptions import NoDriverFoundError, NoResourceFoundError, InvalidConfigError
from ..resource.remote import RemotePlaceManager, RemotePlace
from ..util.dict import diff_dict, flat_dict, filter_dict
from ..util.yaml import dump
from .. import Target, target_factory

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
            self.config.realm, ["ticket"],
            "client/{}/{}".format(gethostname(), getuser())
        )

    def onChallenge(self, challenge):
        return "dummy-ticket"

    @asyncio.coroutine
    def onJoin(self, details):
        # FIXME race condition?
        resources = yield from self.call(
            'org.labgrid.coordinator.get_resources'
        )
        self.resources = {}
        for exporter, groups in resources.items():
            for group_name, group in sorted(groups.items()):
                for resource_name, resource in sorted(group.items()):
                    yield from self.on_resource_changed(
                        exporter, group_name, resource_name, resource
                    )

        places = yield from self.call('org.labgrid.coordinator.get_places')
        self.places = {}
        for placename, config in places.items():
            yield from self.on_place_changed(placename, config)

        yield from self.subscribe(
            self.on_resource_changed,
            'org.labgrid.coordinator.resource_changed'
        )
        yield from self.subscribe(
            self.on_place_changed, 'org.labgrid.coordinator.place_changed'
        )
        yield from self.connected(self)

    @asyncio.coroutine
    def on_resource_changed(
        self, exporter, group_name, resource_name, resource
    ):
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
                print("Resource {}/{}/{} created: {}".format(
                    exporter, group_name, resource_name, resource
                ))
            elif resource and old:
                print("Resource {}/{}/{} changed:".format(
                    exporter, group_name, resource_name,
                ))
                for k, v_old, v_new in diff_dict(flat_dict(old), flat_dict(resource)):
                    print("  {}: {} -> {}".format(k, v_old, v_new))
            else:
                print("Resource {}/{}/{} deleted".format(
                    exporter, group_name, resource_name))

    @asyncio.coroutine
    def on_place_changed(self, name, config):
        if not config:
            del self.places[name]
            if self.monitor:
                print("Place {} deleted".format(name))
            return
        config = config.copy()
        config['name'] = name
        config['matches'
               ] = [ResourceMatch(**match) for match in config['matches']]
        config = filter_dict(config, Place, warn=True)
        place = Place(**config)
        if name not in self.places:
            if self.monitor:
                print("Place {} created: {}".format(name, place))
        else:
            if self.monitor:
                print("Place {} changed:".format(name))
                for k, v_old, v_new in diff_dict(
                        flat_dict(self.places[name].asdict()),
                        flat_dict(place.asdict())):
                    print("  {}: {} -> {}".format(k, v_old, v_new))
        self.places[name] = place

    @asyncio.coroutine
    def monitor(self):
        self.monitor = True
        while True:
            yield from asyncio.sleep(3600.0)

    @asyncio.coroutine
    def complete(self):
        if self.args.type == 'resources':
            for exporter, groups in sorted(self.resources.items()):
                for group_name, group in sorted(groups.items()):
                    for resource_name, resource in sorted(group.items()):
                        print("{}/{}/{}".format(exporter, group_name, resource.cls))
        elif self.args.type == 'places':
            for name, place in sorted(self.places.items()):
                print(name)

    @asyncio.coroutine
    def print_resources(self):
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
        if self.args.verbose:
            for exporter, groups in sorted(filtered.items()):
                print("Exporter '{}':".format(exporter))
                for group_name, group in sorted(groups.items()):
                    print("  Group '{}' ({}/{}/*):".format(group_name, exporter, group_name))
                    for resource_name, resource in sorted(group.items()):
                        print("    Resource '{}' ({}/{}/{}[/{}]):".format(resource_name, exporter, group_name, resource.cls, resource_name))
                        print(indent(pformat(resource.asdict()), prefix="      "))
        else:
            for exporter, groups in sorted(filtered.items()):
                for group_name, group in sorted(groups.items()):
                    for resource_name, resource in sorted(group.items()):
                        print("{}/{}/{}".format(exporter, group_name, resource.cls))

    @asyncio.coroutine
    def print_places(self):
        """Print out the places"""
        for name, place in sorted(self.places.items()):
            if self.args.acquired and place.acquired is None:
                continue
            if self.args.verbose:
                print("Place '{}':".format(name))
                place.show(level=1)
            else:
                line = "{}".format(name)

                if place.aliases:
                    line += " ({})".format(' '.join(place.aliases))

                print("{0:<40s} {1}".format(line, place.comment))

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
        for name, place in self.places.items():
            if pattern in name:
                result.add(name)
            for alias in place.aliases:
                if ':' in alias:
                    namespace, alias = alias.split(':', 1)
                    if namespace != getuser():
                        continue
                    elif alias == pattern:  # prefer user namespace
                        return [name]
                if pattern in alias:
                    result.add(name)
        return list(result)

    def get_place(self, place=None):
        pattern = place or self.args.place
        if pattern is None:
            raise UserError("place pattern not specified")
        places = self._match_places(pattern)
        if not places:
            raise UserError("place pattern {} matches nothing".format(pattern))
        if pattern in places:
            return self.places[pattern]
        if len(places) > 1:
            raise UserError(
                "pattern {} matches multiple places ({})".
                format(pattern, ', '.join(places))
            )
        return self.places[places[0]]

    def get_idle_place(self, place=None):
        place = self.get_place(place)
        if place.acquired:
            raise UserError("place {} is not idle (acquired by {})".format(place.name, place.acquired))
        return place

    def get_acquired_place(self, place=None):
        place = self.get_place(place)
        if not place.acquired:
            raise UserError("place {} is not acquired".format(place.name))
        if gethostname()+'/'+getuser() not in place.allowed:
            host, user = place.acquired.split('/')
            if user != getuser():
                raise UserError("place {} is not acquired by your user, acquired by {}".format(place.name, user))
            if host != gethostname():
                raise UserError("place {} is not acquired on this computer, acquired on {}".format(place.name, host))
        return place

    @asyncio.coroutine
    def print_place(self):
        """Print out the current place and related resources"""
        place = self.get_place()
        print("Place '{}':".format(place.name))
        place.show(level=1)
        if place.acquired:
            for resource_path in place.acquired_resources:
                (exporter, group_name, cls, resource_name) = resource_path
                match = place.getmatch(resource_path)
                name = resource_name
                if match.rename:
                    name = match.rename
                resource = self.resources[exporter][group_name][resource_name]
                print("Acquired resource '{}' ({}/{}/{}/{}):".format(
                    name, exporter, group_name, resource.cls, resource_name))
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
                        print("Matching resource '{}' ({}/{}/{}/{}):".format(
                            name, exporter, group_name, resource.cls, resource_name))
                        print(indent(pformat(resource.asdict()), prefix="  "))

    @asyncio.coroutine
    def add_place(self):
        """Add a place to the coordinator"""
        name = self.args.place
        if not name:
            raise UserError("missing place name. Set with -p <place> or via env var $PLACE")
        if name in self.places:
            raise UserError("{} already exists".format(name))
        res = yield from self.call('org.labgrid.coordinator.add_place', name)
        if not res:
            raise ServerError("failed to add place {}".format(name))
        return res

    @asyncio.coroutine
    def del_place(self):
        """Delete a place from the coordinator"""
        name = self.args.place
        if not name:
            raise UserError("missing place name. Set with -p <place> or via env var $PLACE")
        if name not in self.places:
            raise UserError("{} does not exist".format(name))
        res = yield from self.call('org.labgrid.coordinator.del_place', name)
        if not res:
            raise ServerError("failed to delete place {}".format(name))
        return res

    @asyncio.coroutine
    def add_alias(self):
        """Add an alias for a place on the coordinator"""
        place = self.get_idle_place()
        alias = self.args.alias
        if alias in place.aliases:
            raise UserError(
                "place {} already has alias {}".format(place.name, alias)
            )
        res = yield from self.call(
            'org.labgrid.coordinator.add_place_alias', place.name, alias
        )
        if not res:
            raise ServerError(
                "failed to add alias {} for place {}".format(alias, place.name)
            )
        return res

    @asyncio.coroutine
    def del_alias(self):
        """Delete an alias for a place from the coordinator"""
        place = self.get_idle_place()
        alias = self.args.alias
        if alias not in place.aliases:
            raise UserError("place {} has no alias {}".format(place.name, alias))
        res = yield from self.call(
            'org.labgrid.coordinator.del_place_alias', place.name, alias
        )
        if not res:
            raise ServerError(
                "failed to delete alias {} for place {}".format(alias, place.name)
            )
        return res

    @asyncio.coroutine
    def set_comment(self):
        """Set the comment on a place"""
        place = self.get_place()
        comment = ' '.join(self.args.comment)
        res = yield from self.call(
            'org.labgrid.coordinator.set_place_comment', place.name, comment
        )
        if not res:
            raise ServerError(
                "failed to set comment {} for place {}".format(comment, place.name)
            )
        return res

    @asyncio.coroutine
    def add_match(self):
        """Add a match for a place, making fuzzy matching available to the
        client"""
        place = self.get_idle_place()
        if place.acquired:
            raise UserError("can not change acquired place {}".format(place.name))
        for pattern in self.args.patterns:
            if pattern in map(repr, place.matches):
                print("pattern '{}' exists, skipping".format(pattern))
                continue
            if not (2 <= pattern.count("/") <= 3):
                raise UserError(
                    "invalid pattern format '{}' (use 'exporter/group/cls/name')".
                    format(pattern)
                )
            res = yield from self.call(
                'org.labgrid.coordinator.add_place_match', place.name, pattern
            )
            if not res:
                raise ServerError(
                    "failed to add match {} for place {}".format(pattern, place.name)
                )

    @asyncio.coroutine
    def del_match(self):
        """Delete a match for a place"""
        place = self.get_idle_place()
        if place.acquired:
            raise UserError("can not change acquired place {}".format(place.name))
        for pattern in self.args.patterns:
            if pattern not in map(repr, place.matches):
                print("pattern '{}' not found, skipping".format(pattern))
                continue
            if not (2 <= pattern.count("/") <= 3):
                raise UserError(
                    "invalid pattern format '{}' (use 'exporter/group/cls/name')".
                    format(pattern)
                )
            res = yield from self.call(
                'org.labgrid.coordinator.del_place_match', place.name, pattern
            )
            if not res:
                raise ServerError(
                    "failed to delete match {} for place {}".
                    format(pattern, place.name)
                )

    @asyncio.coroutine
    def add_named_match(self):
        """Add a named match for a place.

        Fuzzy matching is not allowed to avoid accidental names conflicts."""
        place = self.get_idle_place()
        if place.acquired:
            raise UserError("can not change acquired place {}".format(place.name))
        pattern = self.args.pattern
        name = self.args.name
        if pattern in map(repr, place.matches):
            raise UserError("pattern '{}' exists".format(pattern))
        if not (2 <= pattern.count("/") <= 3):
            raise UserError(
                "invalid pattern format '{}' (use 'exporter/group/cls/name')".
                format(pattern)
            )
        if '*' in pattern:
            raise UserError(
                "invalid pattern '{}' ('*' not allowed for named matches)".
                format(pattern)
            )
        if not name:
            raise UserError(
                "invalid name '{}'".
                format(name)
            )
        res = yield from self.call(
            'org.labgrid.coordinator.add_place_match', place.name, pattern, name
        )
        if not res:
            raise ServerError(
                "failed to add match {} for place {}".format(pattern, place.name)
            )

    @asyncio.coroutine
    def acquire(self):
        """Acquire a place, marking it unavailable for other clients"""
        place = self.get_place()
        if place.acquired:
            raise UserError(
                "place {} is already acquired by {}".
                format(place.name, place.acquired)
            )
        res = yield from self.call(
            'org.labgrid.coordinator.acquire_place', place.name
        )
        if not res:
            raise ServerError("failed to acquire place {}".format(place.name))
        else:
            print("acquired place {}".format(place.name))

    @asyncio.coroutine
    def release(self):
        """Release a previously acquired place"""
        place = self.get_place()
        if not place.acquired:
            raise UserError("place {} is not acquired".format(place.name))
        host, user = place.acquired.split('/')
        if user != getuser():
            if not self.args.kick:
                raise UserError(
                    "place {} is acquired by a different user ({}), use --kick if you are sure".format(place.name, place.acquired)
                )
            print("warning: kicking user ({})".format(place.acquired))
        res = yield from self.call(
            'org.labgrid.coordinator.release_place', place.name
        )
        if not res:
            raise ServerError("failed to release place {}".format(place.name))
        else:
            print("released place {}".format(place.name))

    @asyncio.coroutine
    def allow(self):
        """Allow another use access to a previously acquired place"""
        place = self.get_place()
        if not place.acquired:
            raise UserError("place {} is not acquired".format(place.name))
        host, user = place.acquired.split('/')
        if user != getuser():
            raise UserError(
                "place {} is acquired by a different user ({})".format(place.name)
            )
        if not '/' in self.args.user:
            raise UserError(
                "user {} must be in <host>/<username> format".format(self.args.user)
            )
        res = yield from self.call(
            'org.labgrid.coordinator.allow_place', place.name, self.args.user
        )
        if not res:
            raise ServerError("failed to allow {} for place {}".format(self.args.user, place.name))
        else:
            print("allowed {} for place {}".format(self.args.user, place.name))

    def get_target_resources(self, place):
        if not place.acquired:
            raise UserError("place {} is not acquired".format(place.name))
        if gethostname()+'/'+getuser() not in place.allowed:
            host, user = place.acquired.split('/')
            if user != getuser():
                raise UserError("place {} is not acquired by your user, acquired by {}".format(place.name, user))
            if host != gethostname():
                raise UserError("place {} is not acquired on this computer, acquired on {}".format(place.name, host))
        resources = {}
        for resource_path in place.acquired_resources:
            match = place.getmatch(resource_path)
            (exporter, group_name, resource_cls, resource_name) = resource_path
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
            print(args)
            resources.append({resource.cls: args})
        return config

    def env(self):
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
                print("Transitioning into state {}".format(self.args.state))
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
        from ..driver.powerdriver import NetworkPowerDriver, USBPowerDriver
        from ..resource.power import NetworkPowerPort
        from ..resource.remote import NetworkUSBPowerPort
        drv = None
        for resource in target.resources:
            if isinstance(resource, NetworkPowerPort):
                try:
                    drv = target.get_driver(NetworkPowerDriver)
                except NoDriverFoundError:
                    drv = NetworkPowerDriver(target, name=None, delay=delay)
                break
            elif isinstance(resource, NetworkUSBPowerPort):
                try:
                    drv = target.get_driver(USBPowerDriver)
                except NoDriverFoundError:
                    drv = USBPowerDriver(target, name=None, delay=delay)
                break
        if not drv:
            raise UserError("target has no compatible resource available")
        target.activate(drv)
        res = getattr(drv, action)()
        if action == 'get':
            print(
                "power for place {} is {}".format(
                    place.name,
                    'on' if res else 'off',
                )
            )

    def digital_io(self):
        place = self.get_acquired_place()
        action = self.args.action
        name = self.args.name
        target = self._get_target(place)
        from ..resource.modbus import ModbusTCPCoil
        from ..resource.onewireport import OneWirePIO
        from ..driver.modbusdriver import ModbusCoilDriver
        from ..driver.onewiredriver import OneWirePIODriver
        drv = None
        for resource in target.resources:
            if isinstance(resource, ModbusTCPCoil):
                try:
                    drv = target.get_driver(ModbusCoilDriver, name=name)
                except NoDriverFoundError:
                    target.set_binding_map({"coil": name})
                    drv = ModbusCoilDriver(target, name=name)
                break
            elif isinstance(resource, OneWirePIO):
                try:
                    drv = target.get_driver(OneWirePIODriver, name=name)
                except NoDriverFoundError:
                    target.set_binding_map({"port": name})
                    drv = OneWirePIODriver(target, name=name)
                break
        if not drv:
            raise UserError("target has no compatible resource available")
        target.activate(drv)
        if action == 'get':
            print(
                "digital IO {} for place {} is {}".format(
                    resource.name,
                    place.name,
                    'high' if drv.get() else 'low',
                )
            )
        elif action == 'high':
            drv.set(True)
        elif action == 'low':
            drv.set(False)

    def _console(self, place):
        target = self._get_target(place)
        from ..resource import NetworkSerialPort
        try:
            resource = target.get_resource(NetworkSerialPort)
        except KeyError:
            print("resource not found")
            return False

        # check for valid resources
        assert resource.port is not None, "Port is not set"

        call = [
            'microcom', '-s', str(resource.speed), '-t',
            "{}:{}".format(resource.host, resource.port)
        ]
        print("connecting to ", resource, "calling ", " ".join(call))
        res = subprocess.call(call)
        if res:
            print("connection lost")
        return res == 0

    def console(self):
        place = self.get_acquired_place()
        while True:
            res = self._console(place)
            if res:
                break
            if not self.args.loop:
                break
            sleep(1.0)

    def fastboot(self):
        place = self.get_acquired_place()
        args = self.args.fastboot_args
        if len(args) < 1:
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
        drv(*args)

    def bootstrap(self):
        place = self.get_acquired_place()
        args = self.args.filename
        target = self._get_target(place)
        from ..driver.usbloader import IMXUSBDriver, MXSUSBDriver
        from ..driver.openocddriver import OpenOCDDriver
        from ..resource.remote import NetworkMXSUSBLoader, NetworkIMXUSBLoader, NetworkAlteraUSBBlaster
        drv = None
        for resource in target.resources:
            if isinstance(resource, NetworkIMXUSBLoader):
                try:
                    drv = target.get_driver(IMXUSBDriver)
                except NoDriverFoundError:
                    drv = IMXUSBDriver(target, name=None)
                drv.loader.timeout = self.args.wait
                break
            elif isinstance(resource, NetworkMXSUSBLoader):
                try:
                    drv = target.get_driver(MXSUSBDriver)
                except NoDriverFoundError:
                    drv = MXSUSBDriver(target, name=None)
                drv.loader.timeout = self.args.wait
                break
            elif isinstance(resource, NetworkAlteraUSBBlaster):
                args = dict(arg.split('=', 1) for arg in self.args.bootstrap_args)
                try:
                    drv = target.get_driver(OpenOCDDriver)
                except NoDriverFoundError:
                    drv = OpenOCDDriver(target, name=None, **args)
                drv.interface.timeout = self.args.wait
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
        from ..resource.remote import NetworkUSBSDMuxDevice
        drv = None
        for resource in target.resources:
            if isinstance(resource, NetworkUSBSDMuxDevice):
                try:
                    drv = target.get_driver(USBSDMuxDriver)
                except NoDriverFoundError:
                    drv = USBSDMuxDriver(target, name=None)
                break
        if not drv:
            raise UserError("target has no compatible resource available")
        target.activate(drv)
        drv.set_mode(action)

    def _get_ip(self, place):
        target = self._get_target(place)
        from ..resource import EthernetPort
        try:
            resource = target.get_resource(EthernetPort)
        except KeyError:
            print("resource not found")
            return None
        matches = []
        for mac, details in resource.extra.get('macs').items():
            ips = details.get('ips', [])
            if not ips:
                continue
            matches.append((details['timestamp'], ips))
        matches.sort()
        newest = matches[-1][1]
        if len(ips) > 1:
            print("multiple IPs found: {}".format(ips))
            return None
        return newest[0]

    def ssh(self):
        place = self.get_acquired_place()
        ip = self._get_ip(place)
        if not ip:
            return
        args = ['ssh',
                '-l', 'root',
                '-o', 'StrictHostKeyChecking no',
                '-o', 'UserKnownHostsFile /dev/null',
                str(ip),
        ] + self.args.leftover
        print('Note: Using dummy known hosts file.')
        res = subprocess.call(args)
        if res:
            print("connection lost")

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
        target = self._get_target(place)
        from ..driver.usbvideodriver import USBVideoDriver
        from ..resource.remote import NetworkUSBVideo
        drv = None
        try:
            drv = target.get_driver(USBVideoDriver)
        except NoDriverFoundError:
            drv = USBVideoDriver(target, name=None)
        target.activate(drv)
        if quality == 'list':
            default, variants = drv.get_caps()
            for name, caps in variants:
                mark = '*' if default == name else ' '
                print("{} {:<10s} {:s}".format(mark, name, caps))
        else:
            drv.stream(quality)

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
            data = drv.get_screenshot()
            filename = 'tmc-screen_{0:%Y-%m-%d}_{0:%H:%M:%S}.png'.format(datetime.now())
            open(filename, 'wb').write(data)
            print("Saved as {}".format(filename))
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
            print("{:<16s} {:<10s}".format(k, str(v)))

def start_session(url, realm, extra):
    from autobahn.wamp.types import ComponentConfig
    from autobahn.websocket.util import parse_url
    from autobahn.asyncio.websocket import WampWebSocketClientFactory

    loop = asyncio.get_event_loop()
    ready = asyncio.Event()

    @asyncio.coroutine
    def connected(session):
        ready.set()

    if not extra:
        extra = {}
    extra['loop'] = loop
    extra['connected'] = connected

    session = [None]

    def create():
        nonlocal session
        cfg = ComponentConfig(realm, extra)
        session[0] = ClientSession(cfg)
        return session[0]

    transport_factory = WampWebSocketClientFactory(create, url=url)
    _, host, port, _, _, _ = parse_url(url)

    coro = loop.create_connection(transport_factory, host, port)
    (transport, protocol) = loop.run_until_complete(coro)
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

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)7s: %(message)s',
        stream=sys.stderr,
    )

    place = os.environ.get('PLACE', None)
    state = os.environ.get('STATE', None)

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-x',
        '--crossbar',
        metavar='URL',
        type=str,
        default=os.environ.get("LG_CROSSBAR", "ws://127.0.0.1:20408/ws"),
        help="crossbar websocket URL"
    )
    parser.add_argument(
        '-c',
        '--config',
        type=str,
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
    subparser.set_defaults(func=ClientSession.monitor)

    subparser = subparsers.add_parser('resources', aliases=('r',),
                                      help="list available resources")
    subparser.add_argument('-a', '--acquired', action='store_true')
    subparser.add_argument('-e', '--exporter')
    subparser.add_argument('match', nargs='?')
    subparser.set_defaults(func=ClientSession.print_resources)

    subparser = subparsers.add_parser('places', aliases=('p',),
                                      help="list available places")
    subparser.add_argument('-a', '--acquired', action='store_true')
    subparser.set_defaults(func=ClientSession.print_places)

    subparser = subparsers.add_parser('who',
                                      help="list acquired places by user")
    subparser.set_defaults(func=ClientSession.print_who)

    subparser = subparsers.add_parser('show',
                                      help="show a place and related resources",
    )
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
    subparser.set_defaults(func=ClientSession.env)

    subparser = subparsers.add_parser('power',
                                      aliases=('pw',),
                                      help="change (or get) a place's power status")
    subparser.add_argument('action', choices=['on', 'off', 'cycle', 'get'])
    subparser.add_argument('-t', '--delay', type=float, default=1.0, help='wait time between off and on during cycle')
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
    subparser.set_defaults(func=ClientSession.console)

    subparser = subparsers.add_parser('fastboot',
                                      help="run fastboot")
    subparser.add_argument('fastboot_args', metavar='ARG', nargs=argparse.REMAINDER,
                           help='fastboot arguments'
    )
    subparser.add_argument('--wait', type=float, default=10.0)
    subparser.set_defaults(func=ClientSession.fastboot)

    subparser = subparsers.add_parser('bootstrap',
                                      help="start a bootloader")
    subparser.add_argument('-w', '--wait', type=float, default=10.0)
    subparser.add_argument('filename', help='filename to boot on the target')
    subparser.add_argument('bootstrap_args', metavar='ARG', nargs=argparse.REMAINDER,
                           help='extra bootstrap arguments'
    )
    subparser.set_defaults(func=ClientSession.bootstrap)

    subparser = subparsers.add_parser('sd-mux',
                                      help="Switch USB SD Muxer")
    subparser.add_argument('action', choices=['dut', 'host', 'off', 'client'])
    subparser.set_defaults(func=ClientSession.sd_mux)

    subparser = subparsers.add_parser('ssh',
                                      help="connect via ssh (with optional arguments)")
    subparser.set_defaults(func=ClientSession.ssh)

    subparser = subparsers.add_parser('telnet',
                                      help="connect via telnet")
    subparser.set_defaults(func=ClientSession.telnet)

    subparser = subparsers.add_parser('video',
                                      help="start a video stream")
    subparser.add_argument('-q', '--quality', type=str,
                           help="select a video quality (use 'list' to show options)")
    subparser.set_defaults(func=ClientSession.video)

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

    # make any leftover arguments available for some commands
    args, leftover = parser.parse_known_args()
    if args.command not in ['ssh']:
        args = parser.parse_args()
    else:
        args.leftover = leftover


    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    if not args.config and args.state:
        print("Setting the state requires a configuration file")
        exit(1)

    env = None
    if args.config:
        env = Environment(config_file=args.config)

    role = None
    if env and env.config.get_targets():
        if args.place:
            role = find_role_by_place(env.config.get_targets(), args.place)
            if not role:
                print("RemotePlace {} not found in configuration file".format(args.place), file=sys.stderr)
                exit(1)
            print("Selected role {} from configuration file".format(role))
        else:
            role, args.place = find_any_role_with_place(env.config.get_targets())
            if not role:
                print("No RemotePlace found in configuration file", file=sys.stderr)
                exit(1)
            print("Selected role {} and place {} from configuration file".format(role, args.place))

    extra = {
        'args': args,
        'env': env,
        'role': role,
        'prog': parser.prog,
    }

    if args.command and args.command != 'help':
        session = start_session(args.crossbar,
            os.environ.get("LG_CROSSBAR_REALM", "realm1"), extra)
        exitcode = 0
        try:
            if asyncio.iscoroutinefunction(args.func):
                session.loop.run_until_complete(args.func(session))
            else:
                args.func(session)
        except NoResourceFoundError as e:
            if args.debug:
                traceback.print_exc()
            else:
                print("{}: error: {}".format(parser.prog, e), file=sys.stderr)
            print('\n'.join(["",
                "This may be caused by disconnected exporter or wrong match entries.",
                "You can use the 'show' command to all matching resources.",
            ]), file=sys.stderr)
            exitcode = 1
        except NoDriverFoundError as e:
            if args.debug:
                traceback.print_exc()
            else:
                print("{}: error: {}".format(parser.prog, e), file=sys.stderr)
            print('\n'.join(["",
                "This is likely caused by an error or missing driver in the environment configuration.",
            ]), file=sys.stderr)
            exitcode = 1
        except InvalidConfigError as e:
            if args.debug:
                traceback.print_exc()
            else:
                print("{}: error: {}".format(parser.prog, e), file=sys.stderr)
            print('\n'.join(["",
                "This is likely caused by an error in the environment configuration or invalid",
                "resource information provided by the coordinator.",
            ]), file=sys.stderr)
            exitcode = 1
        except Error as e:
            if args.debug:
                traceback.print_exc()
            else:
                print("{}: error: {}".format(parser.prog, e), file=sys.stderr)
            exitcode = 1
        except KeyboardInterrupt:
            exitcode = 0
        except:
            traceback.print_exc()
            exitcode = 2
        exit(exitcode)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
