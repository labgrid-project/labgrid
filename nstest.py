#!/usr/bin/env python3

import subprocess
import threading
import os

from labgrid.util.agentwrapper import AgentWrapper

PHYS_DEV = "enp1s0f0"

def nsenter_shell(ns_pid: int):
    subprocess.check_call([
        "nsenter", "-t", str(ns_pid), "-U", "-n", "-m", "--preserve-credentials",
    ])


def local():
    aw = AgentWrapper(None)
    netns = aw.load('netns')

    ns_pid = netns.unshare()
    assert ns_pid > 0

    tun_name, tun_fd = netns.create_tun(address="be:df:8f:7a:12:db")

    links = netns.get_links()
    link_names = [link["ifname"] for link in links]
    assert "tap0" in link_names

    subprocess.check_call([
        "sudo",
        "/home/jluebbe/ptx/labgrid-namespaces/labgrid-raw-interface",
        "ns-macvlan", PHYS_DEV, str(ns_pid),
    ])

    links = netns.get_links()
    link_names = [link["ifname"] for link in links]
    assert "macvlan0" in link_names

    nsenter_shell(ns_pid)

def pump_d2p(dev, pipe):
    while True:
        buf = os.read(dev.fileno(), 1522)
        print('Got tap data with length {}'.format(len(buf)))
        pipe.write(len(buf).to_bytes(2))
        pipe.write(buf)
        pipe.flush()

def pump_p2d(pipe, dev):
    while True:
        length = int.from_bytes(pipe.read(2))
        buf = pipe.read(length)
        print('Got vtap data with length {}'.format(len(buf)))
        os.write(dev.fileno(), buf)

def start_pumps(dev, stdin, stdout):
    threading.Thread(target=pump_d2p, args=(dev, stdin)).start()
    threading.Thread(target=pump_p2d, args=(stdout, dev)).start()


def remote():
    r_aw = AgentWrapper('localhost')
    r_netns = r_aw.load('netns')
    r_ns_pid = r_netns.unshare()
    assert r_ns_pid > 0

    l_aw = AgentWrapper(None)
    l_netns = l_aw.load('netns')
    l_ns_pid = l_netns.unshare()
    assert l_ns_pid > 0

    tun_name, tun_fd = l_netns.create_tun(address="be:df:8f:7a:12:db")

    links = l_netns.get_links()
    link_names = [link["ifname"] for link in links]
    assert "tap0" in link_names

    subprocess.check_call([
        "sudo",
        "/home/jluebbe/ptx/labgrid-namespaces/labgrid-raw-interface",
        "ns-macvtap", PHYS_DEV, str(r_ns_pid),
    ])

    links = r_netns.get_links()
    link_names = [link["ifname"] for link in links]
    assert "macvtap0" in link_names

    # start mapvtap helper in r_ns
    helper = subprocess.Popen(
        ["nsenter", "-t", str(r_ns_pid), "-U", "-n", "-m", "--preserve-credentials",
         '/usr/bin/python3', '/home/jluebbe/ptx/labgrid-namespaces/proxyhelper.py', 'macvtap0'],
         stdout = subprocess.PIPE, stdin = subprocess.PIPE,
    )

    # start pump threads between mapvtap helper and tun_fd in l_netns
    start_pumps(tun_fd, helper.stdin, helper.stdout)

    nsenter_shell(l_ns_pid)


if __name__=="__main__":
    #local()
    remote()
