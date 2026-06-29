import socket

import pytest

from labgrid.driver import CanInterfaceDriver
from labgrid.driver.caninterfacedriver import CanFdFrame, CanFilter, CanFrame
from labgrid.resource import NetworkInterface


FRAMES = (
    CanFrame(0x123, b'\x01'),
    CanFrame(0x456, b'\x11\x22\x33\x44\x55\x66\x77\x88'),
    CanFrame(0x789, b'\x44\x33\x22\x11'),
)


FRAMES_FD = (
    CanFdFrame(0x123, b'\x01'),
    CanFdFrame(0x456, b'\x11\x22\x33\x44\x55\x66\x77\x88'),
    CanFdFrame(0x789, b'\x44\x33\x22\x11', flags=CanFdFrame.BRS),
    CanFdFrame(0x765, b'\xff' * 64),
)


def vcan0_exists():
    try:
        socket.if_nametoindex("vcan0")
        return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(not vcan0_exists(), reason="Virtual CAN interface not found")


@pytest.fixture
def vcan():
    sock = socket.socket(socket.PF_CAN, socket.SOCK_RAW | socket.SOCK_NONBLOCK, socket.CAN_RAW)
    sock.bind(("vcan0",))

    return sock


@pytest.mark.parametrize("frame", FRAMES)
def test_can_frames(target, vcan, frame):
    iface = NetworkInterface(target, "vcan", "vcan0")
    can = CanInterfaceDriver(target, "vcan", "500000")
    target.activate(can)

    vcan.send(frame.to_bytes())
    assert can.recv() == frame


@pytest.mark.parametrize("frame", FRAMES_FD)
def test_can_frames_fd(target, vcan, frame):
    iface = NetworkInterface(target, "vcan", "vcan0")
    can = CanInterfaceDriver(target, "vcan", "500000", "2000000")
    target.activate(can)

    vcan.setsockopt(socket.SOL_CAN_RAW, socket.CAN_RAW_FD_FRAMES, 1)

    vcan.send(frame.to_bytes())
    assert can.recv() == frame


def test_can_filer(target, vcan):
    iface = NetworkInterface(target, "vcan", "vcan0")
    can = CanInterfaceDriver(target, "vcan", "500000")
    target.activate(can)

    can.filter([CanFilter(0x123), CanFilter(0x002, 0x003)])

    frame = CanFrame(0x123, b'\x01')
    vcan.send(frame.to_bytes())
    assert can.recv() == frame

    vcan.send(CanFrame(0x321, b'\x02').to_bytes())
    vcan.send(frame.to_bytes())
    assert can.recv() == frame

    vcan.send(CanFrame(0x012, b'\x03').to_bytes())
    assert can.recv()
