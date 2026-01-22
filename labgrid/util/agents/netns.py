#!/usr/bin/env python

import os
import time
import fcntl
import struct
import subprocess
import socket
import errno
from pathlib import Path

#from pyroute2 import IPRoute

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

    # mount again from inside the netns, so that the correct devices are visible
    subprocess.check_call(['mount', '-t', 'sysfs', 'sysfs', '/sys'])
    #subprocess.check_call(['mount', '-t', 'devtmpfs', 'devtmpfs', '/dev'])
    #subprocess.check_call(['mount', '-t', 'proc', 'proc', '/proc'])

    unshared = True

    return os.getpid()


def handle_create_tun(*, address=None):
    dev_tun = os.fdopen(os.open("/dev/net/tun", os.O_RDWR))
    TUNSETIFF = 0x400454ca
    IFF_TAP = 0x0002
    IFF_NO_PI = 0x1000
    ifr = struct.pack('16sH22s', b"tap0", IFF_TAP|IFF_NO_PI, b'\x00'*22)
    fcntl.ioctl(dev_tun, TUNSETIFF, ifr)

    #ipr = IPRoute()
    #ipr.link('set', ifname="tap0", address=address, state="up")
    subprocess.run(["ip", "link", "set", "up", "tap0"], check=True)
    if address:
        subprocess.run(["ip", "link", "set", "address", address, "dev", "tap0"], check=True)

    return ("", dev_tun)


def handle_socket(*args, **kwargs):
    try:
        s = socket.socket(*args, **kwargs)
        return (0, s)
    except OSError as e:
        return (e.errno, -1)

def handle_get_links():
    # TODO: switch to IPRoute
    import json
    output = subprocess.check_output(['ip', '-j', 'link'])
    return json.loads(output)


def handle_get_prefix():
    return ["nsenter", "-t", str(os.getpid()), "-U", "-n", "-m", "--preserve-credentials"]


def handle_get_pid():
    return os.getpid()


def handle_get_intf():
    return "tap0"


def handle_connect(*args, timeout=None, **kwargs):
    for family, socktype, proto, _, sockaddr in socket.getaddrinfo(*args, **kwargs):
        try:
            with socket.socket(family, socktype, proto) as s:
                if timeout is not None:
                    s.settimeout(timeout)

                s.connect(sockaddr)
                return (0, s.dup())

        except OSError as e:
            return (e.errno, -1)

    return (errno.EADDRNOTAVAIL, -1)


def handle_bind(*args, timeout=None, **kwargs):
    for family, socktype, proto, _, sockaddr in socket.getaddrinfo(*args, **kwargs):
        try:
            with socket.socket(family, socktype, proto) as s:
                if timeout is not None:
                    s.settimeout(timeout)

                s.bind(sockaddr)
                return ("", s.dup())

        except OSError as e:
            return (e.errno, -1)

    return (errno.EADDRNOTAVAIL, -1)


methods = {
    "unshare": handle_unshare,
    "create_tun": handle_create_tun,
    "create_socket": handle_socket,
    "get_links": handle_get_links,
    "get_prefix": handle_get_prefix,
    "get_pid": handle_get_pid,
    "get_intf": handle_get_intf,
    "bind": handle_bind,
    "connect": handle_connect,
}
