"""The remote.exporter module exports resources to the coordinator and makes
them available to other clients on the same coordinator"""
import argparse
import asyncio
import logging
import sys
import os
import traceback
import subprocess
from socket import gethostname, socket, AF_INET, SOCK_STREAM
from contextlib import closing

import attr

from autobahn.asyncio.wamp import ApplicationRunner, ApplicationSession

from .config import ResourceConfig
from .common import ResourceEntry, enable_tcp_nodelay

try:
    import pkg_resources
    __version__ = pkg_resources.get_distribution('labgrid').version
except:
    __version__ = "unknown"

def get_free_port():
    """Helper function to always return an unused port."""
    with closing(socket(AF_INET, SOCK_STREAM)) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


exports = {}
reexec = False

@attr.s(cmp=False)
class ResourceExport(ResourceEntry):
    """Represents a local resource exported via a specific protocol.

    The ResourceEntry attributes contain the information for the client.
    """
    host = attr.ib(default=gethostname(), validator=attr.validators.instance_of(str))
    local = attr.ib(init=False)
    local_params = attr.ib(init=False)
    start_params = attr.ib(init=False)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.logger = logging.getLogger("ResourceExport({})".format(self.cls))
        # move the params to local_params
        self.local_params = self.params.copy()
        for key in self.local_params:
            del self.params[key]
        self.start_params = None

    def _get_start_params(self):
        return {}

    def _get_params(self):
        return {}

    def _start(self, start_params):
        """Start exporting the local resource"""
        pass

    def _stop(self, start_params):
        """Stop exporting the local resource"""
        pass

    def start(self):
        start_params = self._get_start_params()
        self._start(start_params)
        self.start_params = start_params

    def stop(self):
        self._stop(self.start_params)
        self.start_params = None

    def need_restart(self):
        """
        Check if the previously used start parameters have changed so that a
        restart is needed.
        """
        start_params = self._get_start_params()
        if self.start_params != start_params:
            self.logger.info("restart needed ({} -> {})".format(self.start_params, start_params))
            return True
        return False

    def poll(self):
        dirty = False
        # poll and check for updated params/avail
        self.local.poll()
        if self.avail != self.local.avail:
            if self.local.avail:
                self.start()
            else:
                self.stop()
            self.data['avail'] = self.local.avail
            dirty = True
        params = self._get_params()
        if self.params != params:
            if self.local.avail and self.need_restart():
                self.stop()
                self.start()
            self.data['params'].update(params)
            dirty = True
        return dirty


@attr.s(cmp=False)
class USBSerialPortExport(ResourceExport):
    """ResourceExport for a USB SerialPort"""

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.data['cls'] = "NetworkSerialPort"
        from ..resource.udev import USBSerialPort
        self.local = USBSerialPort(target=None, name=None,
                **self.local_params)
        self.child = None
        self.port = None

    def __del__(self):
        if self.child is not None:
            self._stop()

    def _get_start_params(self):
        return {
            'path': self.local.port,
        }

    def _get_params(self):
        """Helper function to return parameters"""
        return {
            'host': self.host,
            'port': self.port,
            'extra': {
                'path': self.local.port,
            }
        }

    def _start(self, start_params):
        """Start ``ser2net`` subprocess"""
        assert self.local.avail
        assert self.child is None
        # start ser2net
        self.port = get_free_port()
        self.child = subprocess.Popen([
            '/usr/sbin/ser2net',
            '-d',
            '-n',
            '-C',
            '{}:telnet:0:{}:115200 8DATABITS NONE 1STOPBIT'.format(
                self.port, start_params['path']
            ),
        ])
        self.logger.info("started ser2net for {} on port {}".format(
            start_params['path'], self.port))

    def _stop(self, start_params):
        """Stop spawned subprocess"""
        assert self.child
        # stop ser2net
        child = self.child
        self.child = None
        child.terminate()
        try:
            child.wait(1.0)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(1.0)
        self.logger.info("stopped ser2net for {} on port {}".format(
            start_params['path'], self.port))


exports["USBSerialPort"] = USBSerialPortExport

@attr.s(cmp=False)
class USBEthernetExport(ResourceExport):
    """ResourceExport for a USB ethernet interface"""

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        from ..resource.udev import USBEthernetInterface
        self.data['cls'] = "EthernetInterface"
        self.local = USBEthernetInterface(target=None, name=None,
                **self.local_params)

    def _get_params(self):
        """Helper function to return parameters"""
        return {
            'ifname': self.local.ifname,
            'extra': {
                'state': self.local.if_state,
            }
        }

exports["USBEthernetInterface"] = USBEthernetExport

@attr.s(cmp=False)
class USBGenericExport(ResourceExport):
    """ResourceExport for USB devices accessed directly from userspace"""

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        local_cls_name = self.cls
        self.data['cls'] = "Network{}".format(self.cls)
        from ..resource import udev
        local_cls = getattr(udev, local_cls_name)
        self.local = local_cls(target=None, name=None,
                **self.local_params)

    def _get_params(self):
        """Helper function to return parameters"""
        return {
            'host': self.host,
            'busnum': self.local.busnum,
            'devnum': self.local.devnum,
            'path': self.local.path,
            'vendor_id': self.local.vendor_id,
            'model_id': self.local.model_id,
        }

@attr.s(cmp=False)
class USBSigrokExport(USBGenericExport):
    """ResourceExport for USB devices accessed directly from userspace"""

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    def _get_params(self):
        """Helper function to return parameters"""
        return {
            'host': self.host,
            'busnum': self.local.busnum,
            'devnum': self.local.devnum,
            'path': self.local.path,
            'vendor_id': self.local.vendor_id,
            'model_id': self.local.model_id,
            'driver': self.local.driver,
            'channels': self.local.channels
        }

@attr.s(cmp=False)
class USBSDMuxExport(USBGenericExport):
    """ResourceExport for USB devices accessed directly from userspace"""

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    def _get_params(self):
        """Helper function to return parameters"""
        return {
            'host': gethostname(),
            'busnum': self.local.busnum,
            'devnum': self.local.devnum,
            'path': self.local.path,
            'vendor_id': self.local.vendor_id,
            'model_id': self.local.model_id,
            'control_path': self.local.control_path,
        }

@attr.s(cmp=False)
class USBPowerPortExport(USBGenericExport):
    """ResourceExport for ports on switchable USB hubs"""

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    def _get_params(self):
        """Helper function to return parameters"""
        return {
            'host': gethostname(),
            'busnum': self.local.busnum,
            'devnum': self.local.devnum,
            'path': self.local.path,
            'vendor_id': self.local.vendor_id,
            'model_id': self.local.model_id,
            'index': self.local.index,
        }


exports["AndroidFastboot"] = USBGenericExport
exports["IMXUSBLoader"] = USBGenericExport
exports["MXSUSBLoader"] = USBGenericExport
exports["AlteraUSBBlaster"] = USBGenericExport
exports["SigrokUSBDevice"] = USBSigrokExport
exports["USBSDMuxDevice"] = USBSDMuxExport

exports["USBMassStorage"] = USBGenericExport
exports["USBVideo"] = USBGenericExport
exports["USBTMC"] = USBGenericExport
exports["USBPowerPort"] = USBPowerPortExport


@attr.s
class EthernetPortExport(ResourceExport):
    """ResourceExport for a ethernet interface"""

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        from ..resource.ethernetport import SNMPEthernetPort
        self.data['cls'] = "EthernetPort"
        self.local = SNMPEthernetPort(target=None, name=None,
                **self.local_params)

    def _get_params(self):
        """Helper function to return parameters"""
        return {
            'switch': self.local.switch,
            'interface': self.local.interface,
            'extra': self.local.extra
        }

exports["SNMPEthernetPort"] = EthernetPortExport


class ExporterSession(ApplicationSession):
    def onConnect(self):
        """Set up internal datastructures on successful connection:
        - Setup loop, name, authid and address
        - Join the coordinator as an exporter"""
        self.loop = self.config.extra['loop']
        self.name = self.config.extra['name']
        self.hostname = self.config.extra['hostname']
        self.authid = "exporter/{}".format(self.name)
        self.address = self._transport.transport.get_extra_info('sockname')[0]
        self.poll_task = None

        self.groups = {}

        enable_tcp_nodelay(self)
        self.join(self.config.realm, ["ticket"], self.authid)

    def onChallenge(self, challenge):
        """Function invoked on received challege, returns just a dummy ticket
        at the moment, authentication is not supported yet"""
        return "dummy-ticket"

    async def onJoin(self, details):
        """On successful join:
        - export available resources
        - bail out if we are unsuccessful
        """
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
                    await self.add_resource(
                        group_name, resource_name, cls, params
                    )

        except:
            traceback.print_exc()
            self.loop.stop()
            return

        self.poll_task = self.loop.create_task(self.poll())

        prefix = 'org.labgrid.exporter.{}'.format(self.name)
        await self.register(self.acquire, '{}.acquire'.format(prefix))
        await self.register(self.release, '{}.release'.format(prefix))
        await self.register(self.version, '{}.version'.format(prefix))

    async def onLeave(self, details):
        """Cleanup after leaving the coordinator connection"""
        if self.poll_task:
            self.poll_task.cancel()
            await asyncio.wait([self.poll_task])
        super().onLeave(details)

    async def onDisconnect(self):
        print("connection lost")
        global reexec
        reexec = True
        if self.poll_task:
            self.poll_task.cancel()
            await asyncio.wait([self.poll_task])
            await asyncio.sleep(0.5) # give others a chance to clean up
        self.loop.stop()

    async def acquire(self, group_name, resource_name):
        resource = self.groups[group_name][resource_name]
        #resource.acquire()
        await self.update_resource(group_name, resource_name)

    async def release(self, group_name, resource_name):
        resource = self.groups[group_name][resource_name]
        #resource.release()
        await self.update_resource(group_name, resource_name)

    async def version(self):
        return __version__

    async def _poll_step(self):
        for group_name, group in self.groups.items():
            for resource_name, resource in group.items():
                if not isinstance(resource, ResourceExport):
                    continue
                try:
                    changed = resource.poll()
                except:
                    print("Exception while polling {}".format(resource), file=sys.stderr)
                    traceback.print_exc()
                    continue
                if changed:
                    # resource has changed
                    data = resource.asdict()
                    print(data)
                    await self.call(
                        'org.labgrid.coordinator.set_resource', group_name,
                        resource_name, data
                    )

    async def poll(self):
        while True:
            try:
                await asyncio.sleep(1.0)
                await self._poll_step()
            except asyncio.CancelledError:
                break
            except:
                traceback.print_exc()

    async def add_resource(self, group_name, resource_name, cls, params):
        """Add a resource to the exporter and update status on the coordinator"""
        print(
            "add resource {}/{}: {}/{}".
            format(group_name, resource_name, cls, params)
        )
        group = self.groups.setdefault(group_name, {})
        assert resource_name not in group
        export_cls = exports.get(cls, ResourceEntry)
        config = {
            'avail': export_cls is ResourceEntry,
            'cls': cls,
            'params': params,
        }
        if issubclass(export_cls, ResourceExport):
            group[resource_name] = export_cls(config, host=self.hostname)
        else:
            group[resource_name] = export_cls(config)
        await self.update_resource(group_name, resource_name)

    async def update_resource(self, group_name, resource_name):
        """Update status on the coordinator"""
        resource = self.groups[group_name][resource_name]
        data = resource.asdict()
        print(data)
        await self.call(
            'org.labgrid.coordinator.set_resource', group_name, resource_name,
            data
        )


def main():
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
        '-n',
        '--name',
        dest='name',
        type=str,
        default=None,
        help='public name of this exporter (defaults to the system hostname)'
    )
    parser.add_argument(
        '--hostname',
        dest='hostname',
        type=str,
        default=None,
        help='hostname (or IP) published for accessing resources (defaults to the system hostname)'
    )
    parser.add_argument(
        '-d',
        '--debug',
        action='store_true',
        default=False,
        help="enable debug mode"
    )
    parser.add_argument(
        'resources',
        metavar='RESOURCES',
        type=str,
        help='resource config file name'
    )

    args = parser.parse_args()

    level='debug' if args.debug else 'info'

    extra = {
        'name': args.name or gethostname(),
        'hostname': args.hostname or gethostname(),
        'resources': args.resources,
    }

    crossbar_url = args.crossbar
    crossbar_realm = os.environ.get("LG_CROSSBAR_REALM", "realm1")

    print("crossbar URL: {}".format(crossbar_url))
    print("crossbar realm: {}".format(crossbar_realm))
    print("exporter name: {}".format(extra['name']))
    print("exporter hostname: {}".format(extra['hostname']))
    print("resource config file: {}".format(extra['resources']))

    extra['loop'] = loop = asyncio.get_event_loop()
    if args.debug:
        loop.set_debug(True)
    runner = ApplicationRunner(url=crossbar_url, realm=crossbar_realm, extra=extra)
    runner.run(ExporterSession, log_level=level)
    if reexec:
        exit(100)


if __name__ == "__main__":
    main()
