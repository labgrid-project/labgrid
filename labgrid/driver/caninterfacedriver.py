import json
import os
import select
import socket
import struct
import subprocess
from typing import List

from attrs import define, field

from .common import Driver
from ..factory import target_factory
from ..step import step
from ..util.agentwrapper import AgentWrapper
from ..util.netns import NSSocket
from ..util import Timeout
from ..resource.remote import RemoteNetworkInterface


@define
class CanFrame:
    """CanFrame - CAN frame header and payload received or sent on the CAN socket"""

    id: int = field(repr=lambda value: value.to_bytes(4).hex())
    "CAN ID of the frame"

    data: bytes = field(repr=lambda value: value.hex(), default=b'')
    "List of payload bytes"

    flags: int = field(default=0, kw_only=True)
    "Set of socketcan frame flags for frame"

    mtu = 16
    "Serialized data size"

    header = struct.Struct("=IBB2x")
    "C structure header format description"

    @property
    def len(self) -> int:
        "Length of payload data in the frame"
        return len(self.data)

    @classmethod
    def from_bytes(cls, data: bytes) -> "CanFrame":
        """Deserialize frame data received from CAN socket"""
        id_, len_, flags = cls.header.unpack_from(data)
        return cls(id_, data[8:8+len_], flags=flags)

    def to_bytes(self) -> bytes:
        """Serialize frame data to write to CAN socket"""
        header = self.header.pack(self.id, self.len, self.flags)
        return (header + self.data).ljust(self.mtu, b"\x00")


@define
class CanFdFrame(CanFrame):
    """CanFdFrame - CAN-FD frame header and payload received or sent on the CAN socket

    See ``CanFrame`` description for details.
    """

    BRS = 0x01
    ESI = 0x02
    FDF = 0x04

    def __attrs_post_init__(self):
        # The FD frame flag is always implied for CAN-FD frames
        self.flags |= self.FDF

    mtu = 72
    "Serialized data size"


@define
class CanFilter:
    """Canfilter - Configuration for a single filter item on the CAN socket"""

    id: int = field(repr=lambda value: value.to_bytes(4).hex())
    "The CAN ID to match against in the filter"

    mask: int | None = field(repr=lambda value: value.to_bytes(4).hex(), default=None)
    "The mask to apply on the configured and received CAN ids before comparing their values"

    header = struct.Struct("=II")

    def __attrs_post_init__(self):
        if self.mask is None:
            self.mask = self.id

    def to_bytes(self) -> bytes:
        return self.header.pack(self.id, self.mask)


@target_factory.reg_driver
@define(eq=False)
class CanInterfaceDriver(Driver):
    """CanNetworkInterface - Read and write CAN frames, and gain access to a CAN interface

    Opens a socket on the bound CAN interface, and provides method to filter, receive, and
    send frames using that socket.

    For remote CAN interfaces (i.e. on exporters), frames are piped to/from a local virtual
    CAN interface created in a network namespace. External programs that need access to the
    interface should be executed using the command prefix exposed in ``namespace_prefix``.

    Args:
        bitrate (int): The bitrate to configure on the interface
        dbitrate (int): optional, enable CANFD and configure this databitrate
    """

    bindings = {
        "iface": {"RemoteNetworkInterface", "NetworkInterface", "USBNetworkInterface"},
    }
    bitrate: int = field()
    dbitrate: int | None = None

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.remote_pipe = None
        self.local_pipe = None
        self.can = None
        self.ns = None

    def on_activate(self):
        if isinstance(self.iface, RemoteNetworkInterface):
            self.can = self.setup_can_pipe()
        else:
            self.can = self.setup_can()

        if self.dbitrate:
            self.can.setsockopt(socket.SOL_CAN_RAW, socket.CAN_RAW_FD_FRAMES, 1)

        self.can.setsockopt(socket.SOL_CAN_RAW, socket.CAN_RAW_RECV_OWN_MSGS, 0)
        self.can.bind((self.iface.ifname,))

    def on_deactivate(self):
        self.can = self.can.close()

        if isinstance(self.iface, RemoteNetworkInterface):
            self.local_pipe = self.local_pipe.terminate()
            self.remote_pipe = self.remote_pipe.terminate()
            self.ns = None

    @Driver.check_active
    @step(result=True)
    def recv(self, timeout: float = 120.0) -> CanFrame | CanFdFrame:
        """Receive one CAN frame from the socket

        Returns a CanFrame or CanFdFrame with the received data.
        """
        recv_timeout = Timeout(timeout)

        while not recv_timeout.expired:
            readable, _, _ = select.select([self.can], [], [], recv_timeout.remaining)
            if self.can not in readable:
                continue

            data = self.can.recv(CanFdFrame.mtu)
            if len(data) == CanFrame.mtu:
                return CanFrame.from_bytes(data)
            elif len(data) == CanFdFrame.mtu:
                return CanFdFrame.from_bytes(data)

        raise TimeoutError(
            f"Timeout after {recv_timeout.timeout} seconds while reading from can"
        )

    @Driver.check_active
    @step(args=["frame"])
    def send(self, frame: CanFrame | CanFdFrame):
        """Transmit one frame on the CAN socket.

        Args:
            frame (CanFrame | CanFdFrame): Frame to send on the socket.
        """
        self.can.send(frame.to_bytes())

    @Driver.check_active
    @step(args=["filters"], result=True)
    def filter(self, filters: List[CanFilter] | None = None):
        """Disable or configure a list of filters on the CAN socket.

        Args:
            filter(None or [CanFilter]): Pass None to disable all filters, or a list
                                         of filters to configure on the socket.
        """
        if filters is None:
            data = CanFilter(0, 0).to_bytes()
        else:
            data = b''.join([f.to_bytes() for f in filters])

        self.can.setsockopt(socket.SOL_CAN_RAW, socket.CAN_RAW_FILTER, data)

    @Driver.check_active
    @property
    def namespace_prefix(self) -> List[str]:
        if self.ns is None:
            return []

        return self.ns.get_prefix()

    def setup_can(self):
        ifname = self.iface.ifname
        cmd = ["ip", "-json", "-pretty", "-details", "link", "show", "dev", ifname]
        output = subprocess.check_output(cmd)
        settings = json.loads(output)[0]
        kind = settings.get("linkinfo", {}).get("info_kind")

        if kind == "vcan" and os.getuid() == 0:
            # Virtual CAN devices don't require settings
            cmd = ["ip", "link", "set", "dev", ifname, "up"]
            subprocess.check_call(cmd)
        elif kind == "vcan":
            # Verify virtual CAN interface is up
            if "UP" not in settings.get("flags", []):
                raise RuntimeError(f"{ifname} not up")
        elif os.getuid() == 0:
            # Configure CAN interface according to configuration
            cmd_base = ["ip", "link", "set", "dev", ifname]

            subprocess.check_call(cmd_base + ["down"])

            cmd_args = [
                "up",
                "type", "can",
                "bitrate", str(self.bitrate),
            ]

            if self.dbitrate is not None:
                cmd_args += ["dbitrate", str(self.dbitrate)]
                cmd_args += ["fd", "on"]
            else:
                cmd_args += ["fd", "off"]

            subprocess.check_call(cmd_base + cmd_args)
        else:
            # Verify CAN interface settings
            if "UP" not in settings.get("flags", []):
                raise RuntimeError(f"{ifname} not up")

            info_data = settings.get("linkinfo", {}).get("info_data", {})

            bitrate = info_data.get("bittiming", {}).get("bitrate")
            if bitrate != self.bitrate:
                raise RuntimeError(f"{ifname} bitrate mismatch: expected {self.bitrate}; got {bitrate}")

            dbitrate = info_data.get("data_bittiming", {}).get("bitrate")
            if dbitrate != self.dbitrate:
                raise RuntimeError(f"{ifname} dbitrate mismatch: expected {self.dbitrate}; got {dbitrate}")

            controlmode = settings.get("linkinfo", {}).get("info_data", {}).get("ctrlmode", [])
            if self.dbitrate is not None and "FD" not in controlmode:
                raise RuntimeError(f"{ifname} not configured to CAN-FD")

        return socket.socket(socket.PF_CAN, socket.SOCK_RAW | socket.SOCK_NONBLOCK, socket.CAN_RAW)

    def setup_can_pipe(self):
        # Start pipe to/from can interface on remote exporter
        cmd = self.iface.command_prefix
        cmd += ["sudo", "labgrid-raw-interface", "canpipe", self.iface.ifname, str(self.bitrate)]

        if self.dbitrate is not None:
            cmd += [str(self.dbitrate)]

        self.remote_pipe = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )

        # Start pipe to/from vcan interface locally
        wrapper = AgentWrapper()

        self.ns = wrapper.load("netns")
        self.ns.unshare()

        _, can_fd = self.ns.create_vcan(self.iface.ifname, self.dbitrate is not None)

        self.local_pipe = subprocess.Popen(
            ["labgrid-tap-fwd", str(can_fd)],
            stdin=self.remote_pipe.stdout,
            stdout=self.remote_pipe.stdin,
            pass_fds=(can_fd,),
        )

        self.remote_pipe.stdin.close()
        self.remote_pipe.stdout.close()

        # Create namespaced CAN socket to use with vcan interface
        ret, fd = self.ns.create_socket(socket.PF_CAN, socket.SOCK_RAW | socket.SOCK_NONBLOCK, socket.CAN_RAW)
        if "error" in ret:
            raise OSError(*ret["error"])

        return NSSocket(fileno=fd)._attach_remote_sock(ret["id"], self.ns)
