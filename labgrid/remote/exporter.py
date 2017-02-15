import argparse
import asyncio
import logging
import sys
import traceback
import subprocess
from socket import gethostname, socket, AF_INET, SOCK_STREAM
from contextlib import closing

import attr

from autobahn.asyncio.wamp import ApplicationRunner, ApplicationSession

from .config import ResourceConfig
from .common import ResourceEntry

logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)7s: %(message)s',
    stream=sys.stderr,
)

def get_free_port():
    with closing(socket(AF_INET, SOCK_STREAM)) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

exports = {}

@attr.s
class ResourceExport(ResourceEntry):
    """Represents a local resource exported via a specific protocol.

    The ResourceEntry attributes contain the information for the client.
    """
    local = attr.ib(init=False)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        # move the params to local_params
        self.local_params = self.params.copy()
        for key in self.local_params:
            del self.params[key]

    def _get_params(self):
        return {}

    def _start(self):
        pass

    def _stop(self):
        pass

    def poll(self):
        dirty = False
        # poll and check for updated params/avail
        self.local.poll()
        if self.avail != self.local.avail:
            if self.local.avail:
                self._start()
            else:
                self._stop()
            self.data['avail'] = self.local.avail
            dirty = True
        params = self._get_params()
        if self.params != params:
            self.data['params'].update(params)
            dirty = True
        return dirty


@attr.s
class USBSerialPortExport(ResourceExport):
    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.data['cls'] = "NetworkSerialPort"
        from ..resource.udev import USBSerialPort
        self.local = USBSerialPort(None, **self.local_params)
        self.child = None
        self.port = None

    def __del(self):
        if self.child is not None:
            self.stop()

    def _get_params(self):
        return {
            'host': gethostname(),
            'port': self.port,
        }

    def _start(self):
        assert self.local.avail
        assert self.child is None
        # start ser2net
        self.port = get_free_port()
        self.child = subprocess.Popen([
            '/usr/sbin/ser2net', '-d', '-n',
            '-C', '{}:telnet:0:{}:115200 8DATABITS NONE 1STOPBIT'.format(
                self.port, self.local.port),
        ])

    def _stop(self):
        assert self.child
        # stop ser2net
        child = self.child
        self.child = None
        child.kill()
exports["USBSerialPort"] = USBSerialPortExport


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
            resource_config = ResourceConfig(self.config.extra['resources'])
            for group_name, group in resource_config.data.items():
                for resource_name, params in group.items():
                    if resource_name == 'location':
                        continue
                    if params is None:
                        continue
                    cls = params.pop('cls', resource_name)
                    yield from self.add_resource(group_name, resource_name, cls, params)

        except:
            traceback.print_exc()
            self.loop.stop()
            return

        self.poll_task = self.loop.create_task(self.poll())

        prefix = 'org.labgrid.exporter.{}'.format(self.name)
        yield from self.register(self.aquire, '{}.aquire'.format(prefix))
        yield from self.register(self.release, '{}.release'.format(prefix))

    @asyncio.coroutine
    def onLeave(self, details):
        self.poll_task.cancel()
        yield from asyncio.wait([self.poll_task])
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
    def _poll_step(self):
        for group_name, group in self.groups.items():
            for resource_name, resource in group.items():
                if not isinstance(resource, ResourceExport):
                    continue
                if resource.poll():
                    # resource has changed
                    data = resource.asdict()
                    print(data)
                    yield from self.call(
                        'org.labgrid.coordinator.set_resource',
                        group_name, resource_name, data
                    )

    @asyncio.coroutine
    def poll(self):
        while True:
            try:
                yield from self._poll_step()
                yield from asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break
            except:
                traceback.print_exc()

    @asyncio.coroutine
    def add_resource(self, group_name, resource_name, cls, params):
        print("add resource {}/{}: {}/{}".format(group_name, resource_name, cls, params))
        group = self.groups.setdefault(group_name, {})
        assert resource_name not in group
        export_cls = exports.get(cls, ResourceEntry)
        config = {
            'avail': export_cls is ResourceEntry,
            'cls': cls,
            'params': params,
        }
        group[resource_name] = export_cls(config)
        yield from self.update_resource(group_name, resource_name)

    @asyncio.coroutine
    def update_resource(self, group_name, resource_name):
        resource = self.groups[group_name][resource_name]
        data = resource.asdict()
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
