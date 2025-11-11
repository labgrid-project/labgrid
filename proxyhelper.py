# SPDX-License-Identifier: MIT

import sys
import os
import threading
import struct
import fcntl

def open_tap(name, device = '/dev/net/tun'):
    TUNSETIFF = 0x400454ca
    IFF_NO_PI = 0x1000
    O_RDWR = 0x2
    IFF_TAP = 0x0002

    flags = IFF_TAP | IFF_NO_PI
    name = name.encode()
    ifr_name = name + b'\x00' * (16 - len(name))
    ifr = struct.pack('16sH22s', ifr_name, flags, b'\x00'*22)

    fd = os.open(device, O_RDWR)
    fcntl.ioctl(fd, TUNSETIFF, ifr)
    return fd

def open_macvtap(name):
    with open('/sys/class/net/{}/ifindex'.format(name)) as f:
        idx = f.read().strip()
    return open_tap(name = name, device = '/dev/tap' + idx)


vtap = open_macvtap(sys.argv[1])

def t1():
    while True:
        length = int.from_bytes(sys.stdin.buffer.read(2))
        buf = sys.stdin.buffer.read(length)
        os.write(vtap, buf)

threading.Thread(target=t1).start()

while True:
    buf = os.read(vtap, 1522)
    sys.stdout.buffer.write(len(buf).to_bytes(2))
    sys.stdout.buffer.write(buf)
    sys.stdout.buffer.flush()
