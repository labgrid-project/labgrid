"""The remote.exporter module exports resources to the coordinator and makes
them available to other clients on the same coordinator"""

import argparse
import asyncio
import logging
import sys
import os
import os.path
import traceback
import shutil
import subprocess
from urllib.parse import urlsplit
import warnings
from pathlib import Path
from typing import Dict, Type
from socket import gethostname, getfqdn

import attr
import grpc

from .config import ResourceConfig
from .common import ResourceEntry, queue_as_aiter
from .generated import labgrid_coordinator_pb2, labgrid_coordinator_pb2_grpc
from ..util import get_free_port, labgrid_version


exports: Dict[str, Type[ResourceEntry]] = {}
reexec = False


class ExporterError(Exception):
    pass


class BrokenResourceError(ExporterError):
    pass


def log_subprocess_kernel_stack(logger, child):
    if child.poll() is not None:  # nothing to check if no longer running
        return
    try:
        with open(f"/proc/{child.pid}/stack", "r") as f:
            stack = f.read()
            stack = stack.strip()
    except PermissionError:
        return
    logger.info("current kernel stack of %s is:\n%s", child.args, stack)


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
        self.logger = logging.getLogger(f"ResourceExport({self.cls})")
        # move the params to local_params
        self.local_params = self.params.copy()
        for key in self.local_params:
            del self.params[key]
        self.start_params = None
        self._broken = None

    # if something criticial failed for an export, we can mark it as
    # permanently broken
    @property
    def broken(self):
        return self._broken

    @broken.setter
    def broken(self, reason):
        assert self._broken is None
        assert type(reason) == str
        assert reason
        self._broken = reason
        # By setting the acquired field, we block places from using this
        # resource. For now, when trying to acquire a place with a match for
        # this resource, we get 'resource is already in used by <broken>',
        # instead of an unspecific error.
        self.data["acquired"] = "<broken>"
        self.logger.error("marked as broken: %s", reason)

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
        assert not self.broken
        start_params = self._get_start_params()
        try:
            self._start(start_params)
        except Exception as e:
            self.broken = "start failed"
            self.logger.exception("failed to start with %s", start_params)
            raise BrokenResourceError("Failed to start resource") from e
        self.start_params = start_params

    def stop(self):
        assert not self.broken
        try:
            self._stop(self.start_params)
        except Exception:
            self.broken = "stop failed"
            self.logger.exception("failed to stop with %s", self.start_params)
            raise
        self.start_params = None

    def poll(self):
        # poll and check for updated params/avail
        self.local.poll()

        if self.broken:
            pass  # don't touch broken resources
        elif self.local.avail and self.acquired:
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
        if self.avail != (self.local.avail and not self.broken):
            self.data["avail"] = self.local.avail and not self.broken
            dirty = True
        params = self._get_params()
        if not params.get("extra"):
            params["extra"] = {}
        params["extra"]["proxy_required"] = self.proxy_required
        params["extra"]["proxy"] = self.proxy
        if self.broken:
            params["extra"]["broken"] = self.broken
        if self.params != params:
            self.data["params"].update(params)
            dirty = True

        return dirty

    def acquire(self, *args, **kwargs):
        if self.broken:
            raise BrokenResourceError(f"cannot acquire broken resource (original reason): {self.broken}")
        super().acquire(*args, **kwargs)
        self.poll()

    def release(self, *args, **kwargs):
        if self.broken:
            raise BrokenResourceError(f"cannot release broken resource (original reason): {self.broken}")
        super().release(*args, **kwargs)
        self.poll()


@attr.s(eq=False)
class SerialPortExport(ResourceExport):
    """ResourceExport for a USB or Raw SerialPort"""

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.cls == "RawSerialPort":
            from ..resource.serialport import RawSerialPort

            self.local = RawSerialPort(target=None, name=None, **self.local_params)
        elif self.cls == "USBSerialPort":
            from ..resource.udev import USBSerialPort

            self.local = USBSerialPort(target=None, name=None, **self.local_params)
        self.data["cls"] = "NetworkSerialPort"
        self.child = None
        self.port = None
        self.ser2net_bin = shutil.which("ser2net")
        if self.ser2net_bin is None:
            if os.path.isfile("/usr/sbin/ser2net"):
                self.ser2net_bin = "/usr/sbin/ser2net"

            if self.ser2net_bin is None:
                warnings.warn("ser2net binary not found, falling back to /usr/bin/ser2net")
                self.ser2net_bin = "/usr/bin/ser2net"

    def __del__(self):
        if self.child is not None:
            self.stop()

    def _get_start_params(self):
        return {
            "path": self.local.port,
        }

    def _get_params(self):
        """Helper function to return parameters"""
        return {
            "host": self.host,
            "port": self.port,
            "speed": self.local.speed,
            "extra": {
                "path": self.local.port,
            },
        }

    def _start(self, start_params):
        """Start ``ser2net`` subprocess"""
        assert self.local.avail
        assert self.child is None
        assert start_params["path"].startswith("/dev/")
        self.port = get_free_port()

        # Ser2net has switched to using YAML format at version 4.0.0.
        result = subprocess.run([self.ser2net_bin, "-v"], capture_output=True, text=True)
        _, _, version = str(result.stdout).split(" ")
        version = tuple(map(int, version.strip().split(".")))

        # There is a bug in ser2net between 4.4.0 and 4.6.1 where it
        # returns 1 on a successful call to 'ser2net -v'. We don't want
        # a failure because of this, so raise an error only if ser2net
        # is not one of those versions.
        if version not in [(4, 4, 0), (4, 5, 0), (4, 5, 1), (4, 6, 0), (4, 6, 1)] and result.returncode == 1:
            raise ExporterError(f"ser2net {version} returned a nonzero code during version check.")

        if version >= (4, 2, 0):
            cmd = [
                self.ser2net_bin,
                "-d",
                "-n",
                "-Y",
                f"connection: &con01#  accepter: telnet(rfc2217,mode=server),tcp,{self.port}",
                "-Y",
                f'  connector: serialdev(nouucplock=true),{start_params["path"]},{self.local.speed}n81,local',  # pylint: disable=line-too-long
                "-Y",
                "  options:",
                "-Y",
                "    max-connections: 10",
            ]
        else:
            cmd = [
                self.ser2net_bin,
                "-d",
                "-n",
                "-u",
                "-C",
                f'{self.port}:telnet:0:{start_params["path"]}:{self.local.speed} NONE 8DATABITS 1STOPBIT LOCAL',  # pylint: disable=line-too-long
            ]
        self.logger.info("Starting ser2net with: %s", " ".join(cmd))
        self.child = subprocess.Popen(cmd)
        try:
            self.child.wait(timeout=0.5)
            raise ExporterError(f"ser2net for {start_params['path']} exited immediately")
        except subprocess.TimeoutExpired:
            # good, ser2net didn't exit immediately
            pass
        self.logger.info("started ser2net for %s on port %d", start_params["path"], self.port)

    def _stop(self, start_params):
        """Stop ``ser2net`` subprocess"""
        assert self.child
        child = self.child
        self.child = None
        port = self.port
        self.port = None
        child.terminate()
        try:
            child.wait(2.0)  # ser2net takes about a second to react
        except subprocess.TimeoutExpired:
            self.logger.warning("ser2net for %s still running after SIGTERM", start_params["path"])
            log_subprocess_kernel_stack(self.logger, child)
            child.kill()
            child.wait(1.0)
        self.logger.info("stopped ser2net for %s on port %d", start_params["path"], port)


exports["USBSerialPort"] = SerialPortExport
exports["RawSerialPort"] = SerialPortExport


@attr.s(eq=False)
class NetworkInterfaceExport(ResourceExport):
    """ResourceExport for a network interface"""

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.cls == "NetworkInterface":
            from ..resource.base import NetworkInterface

            self.local = NetworkInterface(target=None, name=None, **self.local_params)
        elif self.cls == "USBNetworkInterface":
            from ..resource.udev import USBNetworkInterface

            self.local = USBNetworkInterface(target=None, name=None, **self.local_params)
        self.data["cls"] = "RemoteNetworkInterface"

    def _get_params(self):
        """Helper function to return parameters"""
        params = {
            "host": self.host,
            "ifname": self.local.ifname,
        }
        if self.cls == "USBNetworkInterface":
            params["extra"] = {
                "state": self.local.if_state,
            }

        return params


exports["USBNetworkInterface"] = NetworkInterfaceExport
exports["NetworkInterface"] = NetworkInterfaceExport


@attr.s(eq=False)
class USBGenericExport(ResourceExport):
    """ResourceExport for USB devices accessed directly from userspace"""

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        local_cls_name = self.cls
        self.data["cls"] = f"Network{self.cls}"
        from ..resource import udev

        local_cls = getattr(udev, local_cls_name)
        self.local = local_cls(target=None, name=None, **self.local_params)

    def _get_params(self):
        """Helper function to return parameters"""
        return {
            "host": self.host,
            "busnum": self.local.busnum,
            "devnum": self.local.devnum,
            "path": self.local.path,
            "vendor_id": self.local.vendor_id,
            "model_id": self.local.model_id,
        }


@attr.s(eq=False)
class USBSigrokExport(USBGenericExport):
    """ResourceExport for USB devices accessed directly from userspace"""

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    def _get_params(self):
        """Helper function to return parameters"""
        return {
            "host": self.host,
            "busnum": self.local.busnum,
            "devnum": self.local.devnum,
            "path": self.local.path,
            "vendor_id": self.local.vendor_id,
            "model_id": self.local.model_id,
            "driver": self.local.driver,
            "channels": self.local.channels,
        }


@attr.s(eq=False)
class USBSDMuxExport(USBGenericExport):
    """ResourceExport for USB devices accessed directly from userspace"""

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    def _get_params(self):
        """Helper function to return parameters"""
        return {
            "host": self.host,
            "busnum": self.local.busnum,
            "devnum": self.local.devnum,
            "path": self.local.path,
            "vendor_id": self.local.vendor_id,
            "model_id": self.local.model_id,
            "control_path": self.local.control_path,
        }


@attr.s(eq=False)
class USBSDWireExport(USBGenericExport):
    """ResourceExport for USB devices accessed directly from userspace"""

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    def _get_params(self):
        """Helper function to return parameters"""
        return {
            "host": self.host,
            "busnum": self.local.busnum,
            "devnum": self.local.devnum,
            "path": self.local.path,
            "vendor_id": self.local.vendor_id,
            "model_id": self.local.model_id,
            "control_serial": self.local.control_serial,
        }


@attr.s(eq=False)
class USBAudioInputExport(USBGenericExport):
    """ResourceExport for ports on switchable USB hubs"""

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    def _get_params(self):
        """Helper function to return parameters"""
        return {
            "host": self.host,
            "busnum": self.local.busnum,
            "devnum": self.local.devnum,
            "path": self.local.path,
            "vendor_id": self.local.vendor_id,
            "model_id": self.local.model_id,
            "index": self.local.index,
            "alsa_name": self.local.alsa_name,
        }


@attr.s(eq=False)
class SiSPMPowerPortExport(USBGenericExport):
    """ResourceExport for ports on GEMBRID switches"""

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    def _get_params(self):
        """Helper function to return parameters"""
        return {
            "host": self.host,
            "busnum": self.local.busnum,
            "devnum": self.local.devnum,
            "path": self.local.path,
            "vendor_id": self.local.vendor_id,
            "model_id": self.local.model_id,
            "index": self.local.index,
        }


@attr.s(eq=False)
class USBPowerPortExport(USBGenericExport):
    """ResourceExport for ports on switchable USB hubs"""

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    def _get_params(self):
        """Helper function to return parameters"""
        return {
            "host": self.host,
            "busnum": self.local.busnum,
            "devnum": self.local.devnum,
            "path": self.local.path,
            "vendor_id": self.local.vendor_id,
            "model_id": self.local.model_id,
            "index": self.local.index,
        }


@attr.s(eq=False)
class USBDeditecRelaisExport(USBGenericExport):
    """ResourceExport for outputs on deditec relais"""

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    def _get_params(self):
        """Helper function to return parameters"""
        return {
            "host": self.host,
            "busnum": self.local.busnum,
            "devnum": self.local.devnum,
            "path": self.local.path,
            "vendor_id": self.local.vendor_id,
            "model_id": self.local.model_id,
            "index": self.local.index,
        }


@attr.s(eq=False)
class USBHIDRelayExport(USBGenericExport):
    """ResourceExport for outputs on simple USB HID relays"""

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    def _get_params(self):
        """Helper function to return parameters"""
        return {
            "host": self.host,
            "busnum": self.local.busnum,
            "devnum": self.local.devnum,
            "path": self.local.path,
            "vendor_id": self.local.vendor_id,
            "model_id": self.local.model_id,
            "index": self.local.index,
        }


@attr.s(eq=False)
class USBFlashableExport(USBGenericExport):
    """ResourceExport for Flashable USB devices"""

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    def _get_params(self):
        p = super()._get_params()
        p["devnode"] = self.local.devnode
        return p


@attr.s(eq=False)
class USBGenericRemoteExport(USBGenericExport):
    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.data["cls"] = f"Remote{self.cls}".replace("Network", "")


exports["AndroidFastboot"] = USBGenericExport
exports["AndroidUSBFastboot"] = USBGenericRemoteExport
exports["DFUDevice"] = USBGenericExport
exports["IMXUSBLoader"] = USBGenericExport
exports["MXSUSBLoader"] = USBGenericExport
exports["RKUSBLoader"] = USBGenericExport
exports["AlteraUSBBlaster"] = USBGenericExport
exports["SigrokUSBDevice"] = USBSigrokExport
exports["SigrokUSBSerialDevice"] = USBSigrokExport
exports["USBSDMuxDevice"] = USBSDMuxExport
exports["USBSDWireDevice"] = USBSDWireExport
exports["USBDebugger"] = USBGenericExport

exports["USBMassStorage"] = USBGenericExport
exports["USBVideo"] = USBGenericExport
exports["USBAudioInput"] = USBAudioInputExport
exports["USBTMC"] = USBGenericExport
exports["SiSPMPowerPort"] = SiSPMPowerPortExport
exports["USBPowerPort"] = USBPowerPortExport
exports["DeditecRelais8"] = USBDeditecRelaisExport
exports["HIDRelay"] = USBHIDRelayExport
exports["USBFlashableDevice"] = USBFlashableExport
exports["LXAUSBMux"] = USBGenericExport


@attr.s(eq=False)
class ProviderGenericExport(ResourceExport):
    """ResourceExport for Resources derived from BaseProvider"""

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        local_cls_name = self.cls
        self.data["cls"] = f"Remote{self.cls}"
        from ..resource import provider

        local_cls = getattr(provider, local_cls_name)
        self.local = local_cls(target=None, name=None, **self.local_params)

    def _get_params(self):
        """Helper function to return parameters"""
        return {
            "host": self.host,
            "internal": self.local.internal,
            "external": self.local.external,
        }


exports["TFTPProvider"] = ProviderGenericExport
exports["NFSProvider"] = ProviderGenericExport
exports["HTTPProvider"] = ProviderGenericExport


@attr.s
class EthernetPortExport(ResourceExport):
    """ResourceExport for a ethernet interface"""

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        from ..resource.ethernetport import SNMPEthernetPort

        self.data["cls"] = "EthernetPort"
        self.local = SNMPEthernetPort(target=None, name=None, **self.local_params)

    def _get_params(self):
        """Helper function to return parameters"""
        return {"switch": self.local.switch, "interface": self.local.interface, "extra": self.local.extra}


exports["SNMPEthernetPort"] = EthernetPortExport


@attr.s(eq=False)
class GPIOSysFSExport(ResourceExport):
    _gpio_sysfs_path_prefix = "/sys/class/gpio"

    """ResourceExport for GPIO lines accessed directly from userspace"""

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.cls == "SysfsGPIO":
            from ..resource.base import SysfsGPIO

            self.local = SysfsGPIO(target=None, name=None, **self.local_params)
        elif self.cls == "MatchedSysfsGPIO":
            from ..resource.udev import MatchedSysfsGPIO

            self.local = MatchedSysfsGPIO(target=None, name=None, **self.local_params)
        self.data["cls"] = "NetworkSysfsGPIO"
        self.export_path = Path(GPIOSysFSExport._gpio_sysfs_path_prefix, f"gpio{self.local.index}")
        self.system_exported = False

    def _get_params(self):
        """Helper function to return parameters"""
        return {
            "host": self.host,
            "index": self.local.index,
        }

    def _get_start_params(self):
        return {
            "index": self.local.index,
        }

    def _start(self, start_params):
        """Start a GPIO export to userspace"""
        index = start_params["index"]

        if self.export_path.exists():
            self.system_exported = True
            return

        export_sysfs_path = os.path.join(GPIOSysFSExport._gpio_sysfs_path_prefix, "export")
        with open(export_sysfs_path, mode="wb") as export:
            export.write(str(index).encode("utf-8"))

    def _stop(self, start_params):
        """Disable a GPIO export to userspace"""
        index = start_params["index"]

        if self.system_exported:
            return

        export_sysfs_path = os.path.join(GPIOSysFSExport._gpio_sysfs_path_prefix, "unexport")
        with open(export_sysfs_path, mode="wb") as unexport:
            unexport.write(str(index).encode("utf-8"))


exports["SysfsGPIO"] = GPIOSysFSExport
exports["MatchedSysfsGPIO"] = GPIOSysFSExport


@attr.s
class NetworkServiceExport(ResourceExport):
    """ResourceExport for a NetworkService

    This checks if the address has a interface suffix and then provides the
    neccessary proxy information.
    """

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        from ..resource.networkservice import NetworkService

        self.data["cls"] = "NetworkService"
        self.local = NetworkService(target=None, name=None, **self.local_params)
        if "%" in self.local_params["address"]:
            self.proxy_required = True

    def _get_params(self):
        """Helper function to return parameters"""
        return {
            **self.local_params,
        }


exports["NetworkService"] = NetworkServiceExport


@attr.s
class HTTPVideoStreamExport(ResourceExport):
    """ResourceExport for an HTTPVideoStream"""

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        from ..resource.httpvideostream import HTTPVideoStream

        self.data["cls"] = "HTTPVideoStream"
        self.local = HTTPVideoStream(target=None, name=None, **self.local_params)

    def _get_params(self):
        return self.local_params


exports["HTTPVideoStream"] = HTTPVideoStreamExport


@attr.s(eq=False)
class LXAIOBusNodeExport(ResourceExport):
    """ResourceExport for LXAIOBusNode devices accessed via the HTTP API"""

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        local_cls_name = self.cls
        self.data["cls"] = f"Network{self.cls}"
        from ..resource import lxaiobus

        local_cls = getattr(lxaiobus, local_cls_name)
        self.local = local_cls(target=None, name=None, **self.local_params)

    def _get_params(self):
        return self.local_params


exports["LXAIOBusPIO"] = LXAIOBusNodeExport


@attr.s(eq=False)
class AndroidNetFastbootExport(ResourceExport):
    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        local_cls_name = self.cls
        self.data["cls"] = f"Remote{self.cls}"
        from ..resource import fastboot

        local_cls = getattr(fastboot, local_cls_name)
        self.local = local_cls(target=None, name=None, **self.local_params)

    def _get_params(self):
        """Helper function to return parameters"""
        return {"host": self.host, **self.local_params}


exports["AndroidNetFastboot"] = AndroidNetFastbootExport


@attr.s(eq=False)
class YKUSHPowerPortExport(ResourceExport):
    """ResourceExport for YKUSHPowerPort devices"""

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        local_cls_name = self.cls
        self.data["cls"] = f"Network{local_cls_name}"
        from ..resource import ykushpowerport

        local_cls = getattr(ykushpowerport, local_cls_name)
        self.local = local_cls(target=None, name=None, **self.local_params)

    def _get_params(self):
        return {"host": self.host, **self.local_params}


exports["YKUSHPowerPort"] = YKUSHPowerPortExport


class Exporter:
    def __init__(self, config) -> None:
        """Set up internal datastructures on successful connection:
        - Setup loop, name, authid and address
        - Join the coordinator as an exporter"""
        self.config = config
        self.loop = asyncio.get_running_loop()
        self.name = config["name"]
        self.hostname = config["hostname"]
        self.isolated = config["isolated"]

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

        # default to port 20408 if not specified
        if urlsplit(f"//{config['coordinator']}").port is None:
            config["coordinator"] += ":20408"

        self.channel = grpc.aio.insecure_channel(
            target=config["coordinator"],
            options=channel_options,
        )
        self.stub = labgrid_coordinator_pb2_grpc.CoordinatorStub(self.channel)
        self.out_queue = asyncio.Queue()
        self.pump_task = None

        self.poll_task = None

        self.groups = {}

    async def run(self) -> None:
        self.pump_task = self.loop.create_task(self.message_pump())
        self.send_started()

        config_template_env = {
            "env": os.environ,
            "isolated": self.isolated,
            "hostname": self.hostname,
            "name": self.name,
        }
        resource_config = ResourceConfig(self.config["resources"], config_template_env)
        for group_name, group in resource_config.data.items():
            group_name = str(group_name)
            for resource_name, params in group.items():
                resource_name = str(resource_name)
                if resource_name == "location":
                    continue
                if params is None:
                    continue
                cls = params.pop("cls", resource_name)

                # this may call back to acquire the resource immediately
                await self.add_resource(group_name, resource_name, cls, params)

            # flush queued message
            while not self.pump_task.done():
                try:
                    await asyncio.wait_for(self.out_queue.join(), timeout=1)
                    break
                except asyncio.TimeoutError:
                    if self.pump_task.done():
                        await self.pump_task
                        logging.debug("pump task exited, shutting down exporter")
                        return

        logging.info("creating poll task")
        self.poll_task = self.loop.create_task(self.poll())

        (done, pending) = await asyncio.wait((self.pump_task, self.poll_task), return_when=asyncio.FIRST_COMPLETED)
        logging.debug("task(s) %s exited, shutting down exporter", done)
        for task in pending:
            task.cancel()

        await self.pump_task
        await self.poll_task

    def send_started(self):
        msg = labgrid_coordinator_pb2.ExporterInMessage()
        msg.startup.version = labgrid_version()
        msg.startup.name = self.name
        self.out_queue.put_nowait(msg)

    async def message_pump(self):
        got_message = False
        try:
            async for out_message in self.stub.ExporterStream(queue_as_aiter(self.out_queue)):
                got_message = True
                logging.debug("received message %s", out_message)
                kind = out_message.WhichOneof("kind")
                if kind == "hello":
                    logging.info("connected to exporter version %s", out_message.hello.version)
                elif kind == "set_acquired_request":
                    logging.debug("acquire request")
                    success = False
                    reason = None
                    try:
                        if out_message.set_acquired_request.place_name:
                            await self.acquire(
                                out_message.set_acquired_request.group_name,
                                out_message.set_acquired_request.resource_name,
                                out_message.set_acquired_request.place_name,
                            )
                        else:
                            await self.release(
                                out_message.set_acquired_request.group_name,
                                out_message.set_acquired_request.resource_name,
                            )
                        success = True
                    except BrokenResourceError as e:
                        reason = e.args[0]
                    finally:
                        in_message = labgrid_coordinator_pb2.ExporterInMessage()
                        in_message.response.success = success
                        if reason:
                            in_message.response.reason = reason
                        logging.debug("queuing %s", in_message)
                        self.out_queue.put_nowait(in_message)
                        logging.debug("queued %s", in_message)
                else:
                    logging.debug("unknown request: %s", kind)
        except grpc.aio.AioRpcError as e:
            self.out_queue.put_nowait(None)  # let the sender side exit gracefully
            if e.code() == grpc.StatusCode.UNAVAILABLE:
                if got_message:
                    logging.error("coordinator became unavailable: %s", e.details())
                else:
                    logging.error("coordinator is unavailable: %s", e.details())

                global reexec
                reexec = True
            else:
                logging.exception("unexpected grpc error in coordinator message pump task")
        except Exception:
            self.out_queue.put_nowait(None)  # let the sender side exit gracefully
            logging.exception("error in coordinator message pump")

            # only send command response when the other updates have left the queue
            # perhaps with queue join/task_done
            # this should be a command from the coordinator

    async def acquire(self, group_name, resource_name, place_name):
        resource = self.groups.get(group_name, {}).get(resource_name)
        if resource is None:
            logging.error("acquire request for unknown resource %s/%s by %s", group_name, resource_name, place_name)
            return

        try:
            resource.acquire(place_name)
        finally:
            await self.update_resource(group_name, resource_name)

    async def release(self, group_name, resource_name):
        resource = self.groups.get(group_name, {}).get(resource_name)
        if resource is None:
            logging.error("release request for unknown resource %s/%s", group_name, resource_name)
            return

        try:
            resource.release()
        finally:
            await self.update_resource(group_name, resource_name)

    async def _poll_step(self):
        for group_name, group in self.groups.items():
            for resource_name, resource in group.items():
                if not isinstance(resource, ResourceExport):
                    continue
                try:
                    changed = resource.poll()
                except Exception:  # pylint: disable=broad-except
                    print(f"Exception while polling {resource}", file=sys.stderr)
                    traceback.print_exc(file=sys.stderr)
                    continue
                if changed:
                    await self.update_resource(group_name, resource_name)
                else:
                    # let other tasks run, see https://github.com/python/asyncio/issues/284
                    await asyncio.sleep(0)

    async def poll(self):
        while True:
            try:
                await asyncio.sleep(0.25)
                await self._poll_step()
            except asyncio.CancelledError:
                break
            except Exception:  # pylint: disable=broad-except
                traceback.print_exc(file=sys.stderr)

    async def add_resource(self, group_name, resource_name, cls, params):
        """Add a resource to the exporter and update status on the coordinator"""
        print(f"add resource {group_name}/{resource_name}: {cls}/{params}")
        group = self.groups.setdefault(group_name, {})
        assert resource_name not in group
        export_cls = exports.get(cls, ResourceEntry)
        config = {
            "avail": export_cls is ResourceEntry,
            "cls": cls,
            "params": params,
        }
        proxy_req = self.isolated
        if issubclass(export_cls, ResourceExport):
            group[resource_name] = export_cls(config, host=self.hostname, proxy=getfqdn(), proxy_required=proxy_req)
        else:
            config["params"]["extra"] = {
                "proxy": getfqdn(),
                "proxy_required": proxy_req,
            }
            group[resource_name] = export_cls(config)
        await self.update_resource(group_name, resource_name)

    async def update_resource(self, group_name, resource_name):
        """Update status on the coordinator"""
        resource = self.groups[group_name][resource_name]
        msg = labgrid_coordinator_pb2.ExporterInMessage()
        msg.resource.CopyFrom(resource.as_pb2())
        msg.resource.path.group_name = group_name
        msg.resource.path.resource_name = resource_name
        self.out_queue.put_nowait(msg)
        logging.info("queued update for resource %s/%s", group_name, resource_name)


async def amain(config) -> bool:
    exporter = Exporter(config)
    await exporter.run()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--coordinator",
        metavar="HOST:PORT",
        type=str,
        default=os.environ.get("LG_COORDINATOR", "127.0.0.1:20408"),
        help="coordinator host and port",
    )
    parser.add_argument(
        "-n",
        "--name",
        dest="name",
        type=str,
        default=None,
        help="public name of this exporter (defaults to the system hostname)",
    )
    parser.add_argument(
        "--hostname",
        dest="hostname",
        type=str,
        default=None,
        help="hostname (or IP) published for accessing resources (defaults to the system hostname)",
    )
    parser.add_argument(
        "--fqdn", action="store_true", default=False, help="Use fully qualified domain name as default for hostname"
    )
    parser.add_argument("-d", "--debug", action="store_true", default=False, help="enable debug mode")
    parser.add_argument(
        "-i",
        "--isolated",
        action="store_true",
        default=False,
        help="enable isolated mode (always request SSH forwards)",
    )
    parser.add_argument("resources", metavar="RESOURCES", type=str, help="resource config file name")

    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    config = {
        "name": args.name or gethostname(),
        "hostname": args.hostname or (getfqdn() if args.fqdn else gethostname()),
        "resources": args.resources,
        "coordinator": args.coordinator,
        "isolated": args.isolated,
    }

    print(f"exporter name: {config['name']}")
    print(f"exporter hostname: {config['hostname']}")
    print(f"resource config file: {config['resources']}")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    asyncio.run(amain(config), debug=bool(args.debug))

    if reexec:
        exit(100)


if __name__ == "__main__":
    main()
