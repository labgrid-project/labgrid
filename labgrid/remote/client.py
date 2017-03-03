"""The remote.client module contains the functionality to connect to a
coordinator, acquire a place and interact with the connected resources"""
import argparse
import asyncio
import os
import subprocess
import traceback
import logging
import sys
from pprint import pformat
from textwrap import indent
from socket import gethostname
from getpass import getuser
from collections import defaultdict

from autobahn.asyncio.wamp import ApplicationRunner, ApplicationSession

from .common import ResourceEntry, ResourceMatch, Place, enable_tcp_nodelay

logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)7s: %(message)s',
    stream=sys.stderr,
)


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
        self.args = self.config.extra.get('args')
        self.func = self.config.extra.get('func') or self.args.func
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
        try:
            yield from self.func(self)
        except:
            traceback.print_exc()
        if self.args:
            self.loop.stop()

    @asyncio.coroutine
    def on_resource_changed(
        self, exporter, group_name, resource_name, resource
    ):
        #print("Got resource changed: {}/{}/{}, {}".format(
        #    exporter,
        #    group_name,
        #    resource_name,
        #    resource
        #))
        group = self.resources.setdefault(exporter,
                                          {}).setdefault(group_name, {})
        group[resource_name] = ResourceEntry(resource)

    @asyncio.coroutine
    def on_place_changed(self, name, config):
        if not config:
            del self.places[name]
            return
        config = config.copy()
        config['name'] = name
        config['matches'
               ] = [ResourceMatch(**match) for match in config['matches']]
        place = Place(**config)
        #print("Got place changed: {}, {}".format(name, place))
        self.places[name] = place

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

    def _match_places(self, pattern):
        result = set()
        for name, place in self.places.items():
            if pattern in name:
                result.add(name)
            for alias in place.aliases:
                if pattern in alias:
                    result.add(name)
        return list(result)

    def get_place(self, place=None):
        pattern = place or self.args.place
        places = self._match_places(pattern)
        if not places:
            raise UserError("pattern {} matches nothing".format(pattern))
        if len(places) > 1:
            raise UserError(
                "pattern {} matches multiple places ({})".
                format(pattern, ', '.join(places))
            )
        return self.places[places[0]]

    @asyncio.coroutine
    def print_place(self):
        """Print out the current place and related resources"""
        place = self.get_place()
        print("Place '{}':".format(place.name))
        place.show(level=1)
        for (
            exporter, groupname, cls, resourcename
        ) in place.acquired_resources:
            resource = self.resources[exporter][groupname][resourcename]
            print("Resource '{}':".format(resourcename))
            print(indent(pformat(resource.asdict()), prefix="  "))


    @asyncio.coroutine
    def add_place(self):
        """Add a place to the coordinator"""
        name = self.args.place
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
        if name not in self.places:
            raise UserError("{} does not exist".format(name))
        res = yield from self.call('org.labgrid.coordinator.del_place', name)
        if not res:
            raise ServerError("failed to delete place {}".format(name))
        return res

    @asyncio.coroutine
    def add_alias(self):
        """Add an alias for a place on the coordinator"""
        place = self.get_place()
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
        place = self.get_place()
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
        place = self.get_place()
        pattern = self.args.pattern
        if place.acquired:
            raise UserError("can not change acquired place {}".format(place.name))
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
        return res

    @asyncio.coroutine
    def del_match(self):
        """Delete a match for a place"""
        place = self.get_place()
        pattern = self.args.pattern
        if place.acquired:
            raise UserError("can not change acquired place {}".format(place.name))
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
        return res

    @asyncio.coroutine
    def acquire(self):
        """Acquire a place, marking it unavailable for other clients"""
        place = self.get_place()
        if place.acquired:
            raise UserError(
                "place {} is already acquired by {}".
                format(place, place.acquired)
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
        res = yield from self.call(
            'org.labgrid.coordinator.release_place', place.name
        )
        if not res:
            raise ServerError("failed to release place {}".format(place.name))
        else:
            print("released place {}".format(place.name))

    def get_target_config(self, place):
        if not place.acquired:
            raise UserError("place {} is not acquired".format(place.name))
        config = {}
        resources = config['resources'] = {}
        for (
            exporter, groupname, cls, resourcename
        ) in place.acquired_resources:
            resource = self.resources[exporter][groupname][resourcename]
            if not resource.avail:
                continue
            # FIXME handle resourcename here to support multiple resources of the same class
            resources[resource.cls] = resource.params
        return config

    @asyncio.coroutine
    def env(self):
        place = self.get_place()
        env = {'targets': {place.name: self.get_target_config(place)}}
        import yaml
        print(yaml.dump(env))

    def _get_target(self, place):
        target_config = self.get_target_config(place)
        from ..factory import target_factory
        return target_factory.make_target(place.name, target_config)

    @asyncio.coroutine
    def power(self):
        place = self.get_place()
        action = self.args.action
        target = self._get_target(place)
        from ..driver.powerdriver import NetworkPowerDriver
        drv = NetworkPowerDriver(target)
        res = getattr(drv, action)()
        if action == 'get':
            print(
                "power for place {} is {}".format(
                    place.name,
                    'on' if res else 'off',
                )
            )

    def _console(self, place):
        target_config = self.get_target_config(place)
        try:
            resource = target_config['resources']['NetworkSerialPort']
        except KeyError:
            print("resource not found")
            return False
        print("connecting to ", resource)
        res = subprocess.call([
            'microcom', '-t',
            "{}:{}".format(resource['host'], resource['port'])
        ])
        if res:
            print("connection lost")
        return res == 0

    @asyncio.coroutine
    def console(self):
        place = self.get_place()
        while True:
            res = self._console(place)
            if res:
                break
            if not self.args.loop:
                break
            yield from asyncio.sleep(1.0)

    #@asyncio.coroutine
    #def attach(self, place):
    #    usb_devices = devices['usb_devices']
    #    usb_device = usb_devices[place]
    #    print("Attaching to ", usb_device)
    #    subprocess.call([
    #        'usbip', 'attach', '-r', "{}".format(usb_device['host']), '-b',
    #        "{}".format(usb_device['id'])
    #    ])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-x',
        '--crossbar',
        metavar='URL',
        type=str,
        default="ws://127.0.0.1:20408/ws",
        help="crossbar websocket URL"
    )
    subparsers = parser.add_subparsers(
        dest='command',
        title='available subcommands',
        metavar="COMMAND",
    )

    place_parser = argparse.ArgumentParser(add_help=False)
    if 'PLACE' in os.environ:
        place_parser.add_argument(
            '-p',
            '--place',
            type=str,
            required=False,
            default=os.environ.get('PLACE')
        )
    else:
        place_parser.add_argument('-p', '--place', type=str, required=True)

    subparser = subparsers.add_parser('help')

    subparser = subparsers.add_parser('complete')
    subparser.add_argument('type', choices=['resources', 'places'])
    subparser.set_defaults(func=ClientSession.complete)

    subparser = subparsers.add_parser('resources', aliases=('r',),
                                      help="list available resources")
    subparser.add_argument('-a', '--acquired', action='store_true')
    subparser.add_argument('-e', '--exporter')
    subparser.add_argument('-v', '--verbose', action='count', default=0)
    subparser.add_argument('match', nargs='?')
    subparser.set_defaults(func=ClientSession.print_resources)

    subparser = subparsers.add_parser('places', aliases=('p',),
                                      help="list available places")
    subparser.add_argument('-a', '--acquired', action='store_true')
    subparser.add_argument('-v', '--verbose', action='store_true')
    subparser.set_defaults(func=ClientSession.print_places)

    subparser = subparsers.add_parser('show', parents=[place_parser],
        help="show a place and related resources",
    )
    subparser.set_defaults(func=ClientSession.print_place)

    subparser = subparsers.add_parser('add-place', help="add a new place")
    subparser.set_defaults(func=ClientSession.add_place)
    subparser.add_argument('place', help="place name")

    subparser = subparsers.add_parser('del-place', help="delete an existing place")
    subparser.set_defaults(func=ClientSession.del_place)
    subparser.add_argument('place', help="place name")

    subparser = subparsers.add_parser('add-alias', parents=[place_parser],
                                      help="add an alias to a place")
    subparser.add_argument('alias')
    subparser.set_defaults(func=ClientSession.add_alias)

    subparser = subparsers.add_parser('del-alias', parents=[place_parser],
                                      help="delete an alias from a place")
    subparser.add_argument('alias')
    subparser.set_defaults(func=ClientSession.del_alias)

    subparser = subparsers.add_parser('set-comment', parents=[place_parser],
                                      help="update the place comment")
    subparser.add_argument('comment', nargs='+')
    subparser.set_defaults(func=ClientSession.set_comment)

    subparser = subparsers.add_parser('add-match', parents=[place_parser],
                                      help="add a match pattern to a place")
    subparser.add_argument('pattern')
    subparser.set_defaults(func=ClientSession.add_match)

    subparser = subparsers.add_parser('del-match', parents=[place_parser],
                                      help="delete a match pattern from a place")
    subparser.add_argument('pattern')
    subparser.set_defaults(func=ClientSession.del_match)

    subparser = subparsers.add_parser('acquire', parents=[place_parser],
                                      aliases=('lock',),
                                      help="acquire a place")
    subparser.set_defaults(func=ClientSession.acquire)

    subparser = subparsers.add_parser('release', parents=[place_parser],
                                      aliases=('unlock',),
                                      help="release a place")
    subparser.set_defaults(func=ClientSession.release)

    subparser = subparsers.add_parser('env', parents=[place_parser],
                                      help="generate a labgrid environment file for a place")
    subparser.set_defaults(func=ClientSession.env)

    subparser = subparsers.add_parser('power', parents=[place_parser],
                                      help="change (or get) a place's power status")
    subparser.add_argument('action', choices=['on', 'off', 'cycle', 'get'])
    subparser.set_defaults(func=ClientSession.power)

    subparser = subparsers.add_parser('console', parents=[place_parser],
                                      help="connect to the console")
    subparser.add_argument('-l', '--loop', action='store_true',
                           help="keep trying to connect if the console is unavailable")
    subparser.set_defaults(func=ClientSession.console)

    #subparser = subparsers.add_parser('attach', parents=[place_parser])
    #subparser.set_defaults(func=ClientSession.attach)

    args = parser.parse_args()

    extra = {
        'args': args,
    }

    if args.command and args.command != 'help':
        extra['loop'] = loop = asyncio.get_event_loop()
        #loop.set_debug(True)
        runner = ApplicationRunner(
            url=args.crossbar, realm="realm1", extra=extra
        )
        runner.run(ClientSession)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
