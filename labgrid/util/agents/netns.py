#!/usr/bin/env python

import os
import time
import fcntl
import struct
from pathlib import Path

from pyroute2 import IPRoute

import ctypes
import os

CLONE_NEWNS   = 0x00020000  # Mount namespace
CLONE_NEWUSER = 0x10000000  # User namespace
CLONE_NEWNET  = 0x40000000  # Network namespace

libc = ctypes.CDLL("libc.so.6", use_errno=True)

libc.unshare.argtypes = [ctypes.c_int]
libc.unshare.restype = ctypes.c_int

libc.setns.argtypes = [ctypes.c_int, ctypes.c_int]
libc.setns.restype = ctypes.c_int

def unshare(flags):
    ret = libc.unshare(flags)
    if ret != 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err))
    return ret


def setns(fd, nstype=0):
    ret = libc.setns(fd, nstype)
    if ret != 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err))
    return ret


unshared = False
def handle_unshare():
    global unshared
    assert not unshared

    uid = os.getuid()
    gid = os.getgid()

    unshare(CLONE_NEWUSER)
    unshare(CLONE_NEWNET|CLONE_NEWNS)

    uidmap = Path("/proc/self/uid_map")
    uidmap.write_text(f"0 {uid} 1")
    setgroups = Path("/proc/self/setgroups")
    setgroups.write_text(f"deny")
    gidmap = Path("/proc/self/gid_map")
    gidmap.write_text(f"0 {gid} 1")

    unshared = True
    
    return os.getpid()


def handle_create_tun(*, address=None):
    dev_tun = os.fdopen(os.open("/dev/net/tun", os.O_RDWR))
    TUNSETIFF = 0x400454ca
    IFF_TAP = 0x0002
    IFF_NO_PI = 0x1000
    ifr = struct.pack('16sH22s', b"tap0", IFF_TAP|IFF_NO_PI, b'\x00'*22)
    fcntl.ioctl(dev_tun, TUNSETIFF, ifr)

    ipr = IPRoute()
    ipr.link('set', ifname="tap0", address=address, state="up")

    return ("", dev_tun)


def handle_get_links():
    # TODO: switch to IPRoute
    import subprocess
    import json
    output = subprocess.check_output(['ip', '-j', 'link'])
    return json.loads(output)


methods = {
    "unshare": handle_unshare,
    "create_tun": handle_create_tun,
    "get_links": handle_get_links,
}
