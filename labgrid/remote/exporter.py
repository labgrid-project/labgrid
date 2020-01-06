"""The remote.exporter module exports resources to the coordinator and makes
them available to other clients on the same coordinator"""
# pylint: disable=unsupported-assignment-operation
import argparse
import asyncio
import logging
import sys
import os
import time
import traceback
import subprocess
from socket import gethostname, getfqdn
import attr
from autobahn.asyncio.wamp import ApplicationRunner, ApplicationSession

from .config import ResourceConfig
from .common import ResourceEntry, enable_tcp_nodelay
from ..util import get_free_port

try:
    import pkg_resources
    __version__ = pkg_resources.get_distribution('labgrid').version
except pkg_resources.DistributionNotFound:
    __version__ = "unknown"


exports = {}
reexec = False

@attr.s(eq=False)
class ResourceExport(ResourceEntry):
    """Represents a local resource exported via a specific protocol.

    The ResourceEntry attributes contain the information for the client.
    """
    host = attr.ib(default=gethostname(), validator=attr.validators.instance_of(str))
    proxy = attr.ib(default=None)
    proxy_required = attr.ib(default=False)
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

    def _get_start_params(self):  # pylint: disable=no-self-use
        return {}

    def _get_params(self):  # pylint: disable=no-self-use
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

    def poll(self):
        # poll and check for updated params/avail
        self.local.poll()

        if self.local.avail and self.acquired:
            start_params = self._get_start_params()
            if self.start_params is None:
                self.start()
            elif self.start_params != start_params:
                self.logger.info("restart needed (%s -> %s)", self.start_params, start_params)
                self.stop()
                self.start()
        else:
            if self.start_params is not None:
                self.stop()

        # check if resulting information has changed
        dirty = False
        if self.avail != self.local.avail:
            self.data['avail'] = self.local.avail
            dirty = True
        params = self._get_params()
        if not params.get('extra'):
            params['extra'] = {}
        params['extra']['proxy_required'] = self.proxy_required
        params['extra']['proxy'] = self.proxy
        if self.params != params:
            self.data['params'].update(params)  # pylint: disable=unsubscriptable-object
            dirty = True

        return dirty

    def acquire(self, *args, **kwargs):  # pylint: disable=arguments-differ
        super().acquire(*args, **kwargs)
        self.poll()

    def release(self, *args, **kwargs):  # pylint: disable=arguments-differ
        super().release(*args, **kwargs)
        self.poll()


@attr.s(eq=False)
class USBSerialPortExport(ResourceExport):
    """ResourceExport for a USB SerialPort"""

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.data['cls'] = "NetworkSerialPort"
        from ..resource.udev import USBSerialPort
        self.local = USBSerialPort(target=None, name=None, **self.local_params)
        self.child = None
        self.port = None

    def __del__(self):
        if self.child is not None:
            self.stop()

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
            '{}:telnet:0:{}:115200 8DATABITS NONE 1STOPBIT LOCAL'.format(
                self.port, start_params['path']
            ),
        ])
        self.logger.info("started ser2net for %s on port %d", start_params['path'], self.port)

    def _stop(self, start_params):
        """Stop spawned subprocess"""
        assert self.child
        # stop ser2net
        child = self.child
        self.child = None
        port = self.port
        self.port = None
        child.terminate()
        try:
            child.wait(1.0)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(1.0)
        self.logger.info("stopped ser2net for %s on port %d", start_params['path'], port)


exports["USBSerialPort"] = USBSerialPortExport

@attr.s(eq=False)
class USBEthernetExport(ResourceExport):
    """ResourceExport for a USB ethernet interface"""

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        from ..resource.udev import USBEthernetInterface
        self.data['cls'] = "EthernetInterface"
        self.local = USBEthernetInterface(target=None, name=None, **self.local_params)

    def _get_params(self):
        """Helper function to return parameters"""
        return {
            'ifname': self.local.ifname,
            'extra': {
                'state': self.local.if_state,
            }
        }

exports["USBEthernetInterface"] = USBEthernetExport

@attr.s(eq=False)
class USBGenericExport(ResourceExport):
    """ResourceExport for USB devices accessed directly from userspace"""

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        local_cls_name = self.cls
        self.data['cls'] = "Network{}".format(self.cls)
        from ..resource import udev
        local_cls = getattr(udev, local_cls_name)
        self.local = local_cls(target=None, name=None, **self.local_params)

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

@attr.s(eq=False)
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

@attr.s(eq=False)
class USBSDMuxExport(USBGenericExport):
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
            'control_path': self.local.control_path,
        }

@attr.s(eq=False)
class USBPowerPortExport(USBGenericExport):
    """ResourceExport for ports on switchable USB hubs"""

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
            'index': self.local.index,
        }

@attr.s(eq=False)
class USBDeditecRelaisExport(USBGenericExport):
    """ResourceExport for outputs on deditec relais"""

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
            'index': self.local.index,
        }


exports["AndroidFastboot"] = USBGenericExport
exports["IMXUSBLoader"] = USBGenericExport
exports["MXSUSBLoader"] = USBGenericExport
exports["RKUSBLoader"] = USBGenericExport
exports["AlteraUSBBlaster"] = USBGenericExport
exports["SigrokUSBDevice"] = USBSigrokExport
exports["SigrokUSBSerialDevice"] = USBSigrokExport
exports["USBSDMuxDevice"] = USBSDMuxExport

exports["USBMassStorage"] = USBGenericExport
exports["USBVideo"] = USBGenericExport
exports["USBTMC"] = USBGenericExport
exports["USBPowerPort"] = USBPowerPortExport
exports["DeditecRelais8"] = USBDeditecRelaisExport


@attr.s
class EthernetPortExport(ResourceExport):
    """ResourceExport for a ethernet interface"""

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        from ..resource.ethernetport import SNMPEthernetPort
        self.data['cls'] = "EthernetPort"
        self.local = SNMPEthernetPort(target=None, name=None, **self.local_params)

    def _get_params(self):
        """Helper function to return parameters"""
        return {
            'switch': self.local.switch,
            'interface': self.local.interface,
            'extra': self.local.extra
        }

exports["SNMPEthernetPort"] = EthernetPortExport


@attr.s(eq=False)
class GPIOGenericExport(ResourceExport):
    """ResourceExport for GPIO lines accessed directly from userspace"""

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        local_cls_name = self.cls
        self.data['cls'] = "Network{}".format(self.cls)
        from ..resource import udev
        local_cls = getattr(udev, local_cls_name)
        self.local = local_cls(target=None, name=None, **self.local_params)

    def _get_params(self):
        """Helper function to return parameters"""
        return {
            'host': self.host,
            'index': self.local.index,
        }

exports["SysfsGPIO"] = GPIOGenericExport


class ExporterSession(ApplicationSession):
    def onConnect(self):
        """Set up internal datastructures on successful connection:
        - Setup loop, name, authid and address
        - Join the coordinator as an exporter"""
        self.loop = self.config.extra['loop']
        self.name = self.config.extra['name']
        self.hostname = self.config.extra['hostname']
        self.isolated = self.config.extra['isolated']
        self.address = self._transport.transport.get_extra_info('sockname')[0]
        self.checkpoint = time.monotonic()
        self.poll_task = None

        self.groups = {}

        enable_tcp_nodelay(self)
        self.join(self.config.realm, authmethods=["ticket"], authid="exporter/{}".format(
            self.name))

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

        prefix = 'org.labgrid.exporter.{}'.format(self.name)
        await self.register(self.acquire, '{}.acquire'.format(prefix))
        await self.register(self.release, '{}.release'.format(prefix))
        await self.register(self.version, '{}.version'.format(prefix))

        try:
            resource_config = ResourceConfig(self.config.extra['resources'])
            for group_name, group in resource_config.data.items():
                group_name = str(group_name)
                for resource_name, params in group.items():
                    resource_name = str(resource_name)
                    if resource_name == 'location':
                        continue
                    if params is None:
                        continue
                    cls = params.pop('cls', resource_name)

                    # this may call back to acquire the resource immediately
                    await self.add_resource(
                        group_name, resource_name, cls, params
                    )
                    self.checkpoint = time.monotonic()

        except Exception:  # pylint: disable=broad-except
            traceback.print_exc()
            self.loop.stop()
            return

        self.poll_task = self.loop.create_task(self.poll())

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

    async def acquire(self, group_name, resource_name, place_name):
        resource = self.groups[group_name][resource_name]
        resource.acquire(place_name)
        await self.update_resource(group_name, resource_name)

    async def release(self, group_name, resource_name):
        resource = self.groups[group_name][resource_name]
        resource.release()
        await self.update_resource(group_name, resource_name)

    async def version(self):
        self.checkpoint = time.monotonic()
        return __version__

    async def _poll_step(self):
        for group_name, group in self.groups.items():
            for resource_name, resource in group.items():
                if not isinstance(resource, ResourceExport):
                    continue
                try:
                    changed = resource.poll()
                except Exception:  # pylint: disable=broad-except
                    print("Exception while polling {}".format(resource), file=sys.stderr)
                    traceback.print_exc()
                    continue
                if changed:
                    await self.update_resource(group_name, resource_name)

    async def poll(self):
        while True:
            try:
                await asyncio.sleep(0.25)
                await self._poll_step()
            except asyncio.CancelledError:
                break
            except Exception:  # pylint: disable=broad-except
                traceback.print_exc()
            age = time.monotonic() - self.checkpoint
            if age > 300:
                print("missed checkpoint, exiting (last was {} seconds ago)".format(age))
                self.disconnect()

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
        proxy_req = self.isolated
        if issubclass(export_cls, ResourceExport):
            group[resource_name] = export_cls(config, host=self.hostname, proxy=getfqdn(),
                                              proxy_required=proxy_req)
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
        '-i',
        '--isolated',
        action='store_true',
        default=False,
        help="enable isolated mode (always request SSH forwards)"
    )
    parser.add_argument(
        'resources',
        metavar='RESOURCES',
        type=str,
        help='resource config file name'
    )

    args = parser.parse_args()

    level = 'debug' if args.debug else 'info'

    extra = {
        'name': args.name or gethostname(),
        'hostname': args.hostname or gethostname(),
        'resources': args.resources,
        'isolated': args.isolated
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
