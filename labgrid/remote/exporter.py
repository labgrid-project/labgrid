import argparse
import asyncio
import logging
import sys
import traceback
from socket import gethostname

from autobahn.asyncio.wamp import ApplicationRunner, ApplicationSession

from .config import ResourceConfig

logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)7s: %(message)s',
    stream=sys.stderr,
)


class ExporterSession(ApplicationSession):
    def onConnect(self):
        self.loop = self.config.extra['loop']
        self.name = self.config.extra['name']
        self.authid = "exporter/{}".format(self.name)
        self.address = self._transport.transport.get_extra_info('sockname')[0]

        self.groups = {}

        self.join(self.config.realm, ["ticket"], self.authid)

    def onChallenge(self, challenge):
        return "dummy-ticket"

    @asyncio.coroutine
    def onJoin(self, details):
        print(details)
        try:
            self.resource_config = ResourceConfig(self.config.extra['resources'])
            for group_name, group in self.resource_config.data.items():
                for resource_name, resource in group.items():
                    if resource_name == 'location':
                        continue
                    if resource is None:
                        continue
                    resource.setdefault('cls', resource_name)
                    yield from self.add_resource(group_name, resource_name, resource)

        except:
            traceback.print_exc()
            self.loop.stop()
            return

        prefix = 'org.labgrid.exporter.{}'.format(self.name)
        yield from self.register(self.aquire, '{}.aquire'.format(prefix))
        yield from self.register(self.release, '{}.release'.format(prefix))

    @asyncio.coroutine
    def onLeave(self, details):
        #self.uevent_task.cancel()
        #yield from asyncio.wait([self.uevent_task])
        #for resource in self.resources.values():
        #    try:
        #        resource.invalidate()
        #    except ResourceStatusError:
        #        pass
        super().onLeave(details)

    @asyncio.coroutine
    def onDisconnect(self):
        #self.uevent_task.cancel()
        #yield from asyncio.wait([self.uevent_task])
        self.loop.stop()
        print("connection lost")

    @asyncio.coroutine
    def aquire(self, group_name, resource_name):
        resource = self.groups[group_name][resource_name]
        #resource.aquire()
        yield from self.update_resource(group_name, resource_name)

    @asyncio.coroutine
    def release(self, group_name, resource_name):
        resource = self.groups[group_name][resource_name]
        #resource.release()
        yield from self.update_resource(group_name, resource_name)

    @asyncio.coroutine
    def handle_uevents(self):
        while True:
            try:
                client, action, device = yield from self.uevents.get()
                if action == "add":
                    yield from asyncio.shield(self.add_device(device))
                else:
                    yield from asyncio.shield(self.remove_device(device))
            except asyncio.CancelledError:
                break
            except:
                traceback.print_exc()

    @asyncio.coroutine
    def add_resource(self, group_name, resource_name, resource):
        print("add resource {}/{}: {}".format(group_name, resource_name, resource))
        group = self.groups.setdefault(group_name, {})
        assert resource_name not in group
        group[resource_name] = resource
        yield from self.update_resource(group_name, resource_name)

    @asyncio.coroutine
    def remove_resource(self, group_name, resource_name):
        group = self.groups[group_name]
        resource = group.pop(resource_name)
        print("remote resource {}/{}: {}".format(group_name, resource_name, resource))
        #resource.invalidate()
        resource['avail'] = False
        yield from self.update_resource(group_name, resource_name)

    @asyncio.coroutine
    def update_resource(self, group_name, resource_name):
        resource = self.groups[group_name][resource_name]
        #data = resource.serialize()
        data = resource.copy()
        #if not 'address' in data:
        #    data['address'] = self.address
        data['avail'] = True
        print(data)
        yield from self.call(
            'org.labgrid.coordinator.set_resource', group_name, resource_name, data
        )


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
    parser.add_argument(
        '-n',
        '--name',
        dest='name',
        type=str,
        default=gethostname(),
        help='public name of this exporter'
    )
    parser.add_argument(
        'resources',
        metavar='RESOURCES',
        type=str,
        help='resource config file name'
    )

    args = parser.parse_args()

    extra = {
        'name': args.name,
        'resources': args.resources,
    }

    extra['loop'] = loop = asyncio.get_event_loop()
    #loop.set_debug(True)
    runner = ApplicationRunner(url=args.crossbar, realm="realm1", extra=extra)
    runner.run(ExporterSession)

if __name__=="__main__":
    main()
