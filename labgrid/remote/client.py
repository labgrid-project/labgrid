import argparse
import asyncio
import os
import subprocess
import traceback
import logging
import sys
from pprint import pformat, pprint
from textwrap import indent
from socket import gethostname
from getpass import getuser

from autobahn.asyncio.wamp import ApplicationRunner, ApplicationSession

from .common import ResourceEntry, ResourceMatch, Place

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
    def onConnect(self):
        self.loop = self.config.extra['loop']
        self.args = self.config.extra['args']
        self.join(self.config.realm, ["ticket"], "client/{}/{}".format(gethostname(), getuser()))

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
                    yield from self.on_resource_changed(exporter, group_name, resource_name, resource)

        places = yield from self.call(
            'org.labgrid.coordinator.get_places'
        )
        self.places = {}
        for placename, config in places.items():
            yield from self.on_place_changed(placename, config)

        yield from self.subscribe(
            self.on_resource_changed,
            'org.labgrid.coordinator.resource_changed'
        )
        yield from self.subscribe(
            self.on_place_changed,
            'org.labgrid.coordinator.place_changed'
        )
        try:
            yield from self.args.func(self)
        except:
            traceback.print_exc()
        self.loop.stop()

    @asyncio.coroutine
    def on_resource_changed(self, exporter, group_name, resource_name, resource):
        #print("Got resource changed: {}/{}/{}, {}".format(
        #    exporter,
        #    group_name,
        #    resource_name,
        #    resource
        #))
        group = self.resources.setdefault(exporter, {}).setdefault(group_name, {})
        group[resource_name] = resource

    @asyncio.coroutine
    def on_place_changed(self, name, config):
        config = config.copy()
        config['name'] = name
        config['matches'] = [ResourceMatch(**match) for match in config['matches']]
        place = Place(**config)
        #print("Got place changed: {}, {}".format(name, place))
        self.places[name] = place

    @asyncio.coroutine
    def resources(self):
        for exporter, groups in sorted(self.resources.items()):
            print("Exporter '{}':".format(exporter))
            for group_name, group in sorted(groups.items()):
                print("  Group '{}':".format(group_name))
                for resource_name, resource in sorted(group.items()):
                    if not resource['avail']:
                        continue
                    print("    Resource '{}':".format(resource_name))
                    print(indent(pformat(resource), prefix="      "))

    @asyncio.coroutine
    def places(self):
        for name, place in sorted(self.places.items()):
            print("Place '{}':".format(name))
            place.show(level=1)

    def _match_places(self, pattern):
        result = set()
        for name, place in self.places.items():
            if pattern in name:
                result.add(name)
            for alias in place.aliases:
                if pattern in alias:
                    result.add(name)
        return list(result)

    def _get_place(self):
        pattern = self.args.place
        places = self._match_places(pattern)
        if not places:
            raise UserError("pattern {} matches nothing".format(pattern))
        if len(places) > 1:
            raise UserError(
                "pattern {} matches multiple places ({})".
                format(pattern, ', '.join(places))
            )
        return places[0], self.places[places[0]]

    @asyncio.coroutine
    def add_place(self):
        name = self.args.place
        if name in self.places:
            raise UserError("{} already exists".format(name))
        res = yield from self.call(
            'org.labgrid.coordinator.add_place', name
        )
        if not res:
            raise ServerError("failed to add place {}".format(name))
        return res

    @asyncio.coroutine
    def del_place(self):
        name = self.args.place
        if name not in self.places:
            raise UserError("{} does not exist".format(name))
        res = yield from self.call(
            'org.labgrid.coordinator.del_place', name
        )
        if not res:
            raise ServerError("failed to delete place {}".format(name))
        return res

    @asyncio.coroutine
    def add_alias(self):
        place, config = self._get_place()
        alias = self.args.alias
        if alias in config.aliases:
            raise UserError(
                "place {} already has alias {}".format(place, alias)
            )
        res = yield from self.call(
            'org.labgrid.coordinator.add_place_alias', place, alias
        )
        if not res:
            raise ServerError("failed to add alias {} for place {}".format(alias, name))
        return res

    @asyncio.coroutine
    def del_alias(self):
        place, config = self._get_place()
        alias = self.args.alias
        if alias not in config.aliases:
            raise UserError("place {} has no alias {}".format(place, alias))
        res = yield from self.call(
            'org.labgrid.coordinator.del_place_alias', place, alias
        )
        if not res:
            raise ServerError("failed to delete alias {} for place {}".format(alias, name))
        return res

    @asyncio.coroutine
    def set_comment(self):
        place, config = self._get_place()
        comment = self.args.comment
        res = yield from self.call(
            'org.labgrid.coordinator.set_place_comment', place, comment
        )
        if not res:
            raise ServerError("failed to set comment {} for place {}".format(comment, name))
        return res

    @asyncio.coroutine
    def add_match(self):
        place, config = self._get_place()
        pattern = self.args.pattern
        if config.get('aquired'):
            raise UserError("can not change aquired place {}".format(place))
        if not (2 <= pattern.count("/") <= 3):
            raise UserError("invalid pattern format '{}' (use 'exporter/group/cls/name')".format(pattern))
        res = yield from self.call(
            'org.labgrid.coordinator.add_place_match', place, pattern
        )
        if not res:
            raise ServerError("failed to add match {} for place {}".format(pattern, place))
        return res

    @asyncio.coroutine
    def del_match(self):
        place, config = self._get_place()
        resource = [self.args.kind, self.args.exporter, self.args.name]
        if config['aquired']:
            raise UserError("can not change aquired place {}".format(place))
        if resource not in config['resources']:
            raise UserError(
                "place {} has no resource {}".format(place, resource)
            )
        res = yield from self.call(
            'org.labgrid.coordinator.del_place_match', place, pattern
        )
        if not res:
            raise ServerError("failed to delete match {} for place {}".format(pattern, place))
        return res

    @asyncio.coroutine
    def aquire(self):
        place, config = self._get_place()
        if config.aquired:
            raise UserError("place {} is already aquired by {}".format(place, config.aquired))
        res = yield from self.call(
            'org.labgrid.coordinator.aquire_place', place
        )
        if not res:
            raise ServerError("failed to aquire place {}".format(place))
        else:
            print("aquired place {}".format(place))

    @asyncio.coroutine
    def release(self):
        place, config = self._get_place()
        if not config.aquired:
            raise UserError("place {} is not aquired".format(place))
        res = yield from self.call(
            'org.labgrid.coordinator.release_place', place
        )
        if not res:
            raise ServerError("failed to release place {}".format(place))
        else:
            print("released place {}".format(place))

    def _get_target_config(self, place):
        if not place.aquired:
            raise UserError("place {} is not aquired".format(place.name))
        config = {}
        resources = config['resources'] = {}
        for (exporter, groupname, cls, resourcename) in place.aquired_resources:
            resource = self.resources[exporter][groupname][resourcename]
            resources[resourcename] = resource['params']
        return config

    @asyncio.coroutine
    def env(self):
        place, config = self._get_place()
        env = {
            'targets': {
                place: self._get_target_config(config)
            }
        }
        import yaml
        print(yaml.dump(env))

    def _get_target(self, place):
        target_config = self._get_target_config(place)
        from ..factory import target_factory
        return target_factory(place.name, target_config)

    @asyncio.coroutine
    def power(self):
        place, config = self._get_place()
        action = self.args.action
        target = self._get_target(config)
        from ..driver.powerdriver import NetworkPowerDriver
        drv = NetworkPowerDriver(target)
        res = getattr(drv, action)()
        if action == 'get':
            print("power for place {} is {}".format(
                place, 'on' if res else 'off',
            ))

    @asyncio.coroutine
    def connect(self):
        place, config = self._get_place()
        target_config = self._get_target_config(config)
        resource = target_config['resources']['NetworkSerialPort']
        print("Connecting to ", resource)
        subprocess.call([
            'microcom', '-t',
            "{}:{}".format(resource['host'], resource['port'])
        ])

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
        default="ws://127.0.0.1:8080/ws",
        help="crossbar websocket URL"
    )
    subparsers = parser.add_subparsers(dest='command')

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

    subparser = subparsers.add_parser('resources')
    subparser.set_defaults(func=ClientSession.resources)

    subparser = subparsers.add_parser('places')
    subparser.add_argument('-a', '--aquired', action='store_true')
    subparser.set_defaults(func=ClientSession.places)

    subparser = subparsers.add_parser('add-place')
    subparser.set_defaults(func=ClientSession.add_place)
    subparser.add_argument('place')

    subparser = subparsers.add_parser('del-place')
    subparser.set_defaults(func=ClientSession.del_place)
    subparser.add_argument('place')

    subparser = subparsers.add_parser('add-alias', parents=[place_parser])
    subparser.add_argument('alias')
    subparser.set_defaults(func=ClientSession.add_alias)

    subparser = subparsers.add_parser('del-alias', parents=[place_parser])
    subparser.add_argument('alias')
    subparser.set_defaults(func=ClientSession.del_alias)

    subparser = subparsers.add_parser('set-comment', parents=[place_parser])
    subparser.add_argument('comment')
    subparser.set_defaults(func=ClientSession.set_comment)

    subparser = subparsers.add_parser('add-match', parents=[place_parser])
    subparser.add_argument('pattern')
    subparser.set_defaults(func=ClientSession.add_match)

    subparser = subparsers.add_parser('del-match', parents=[place_parser])
    subparser.add_argument('pattern')
    subparser.set_defaults(func=ClientSession.del_match)

    subparser = subparsers.add_parser('aquire', parents=[place_parser])
    subparser.set_defaults(func=ClientSession.aquire)

    subparser = subparsers.add_parser('release', parents=[place_parser])
    subparser.set_defaults(func=ClientSession.release)

    subparser = subparsers.add_parser('env', parents=[place_parser])
    subparser.set_defaults(func=ClientSession.env)

    subparser = subparsers.add_parser('power', parents=[place_parser])
    subparser.add_argument('action', choices=['on', 'off', 'cycle', 'get'])
    subparser.set_defaults(func=ClientSession.power)

    subparser = subparsers.add_parser('connect', parents=[place_parser])
    subparser.set_defaults(func=ClientSession.connect)

    #subparser = subparsers.add_parser('attach', parents=[place_parser])
    #subparser.set_defaults(func=ClientSession.attach)

    args = parser.parse_args()

    extra = {'args': args, }

    if args.command:
        extra['loop'] = loop = asyncio.get_event_loop()
        #loop.set_debug(True)
        runner = ApplicationRunner(
            url=args.crossbar, realm="realm1", extra=extra
        )
        runner.run(ClientSession)
    else:
        parser.print_usage()

if __name__=="__main__":
    main()
