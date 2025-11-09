#!/usr/bin/env python3

from labgrid.util.agentwrapper import AgentWrapper
import subprocess

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
    # TODO
    pass

def pump_p2d(dev, pipe):
    # TODO
    pass


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

    # TODO: start mapvtap helper in r_ns
    # TODO: start pump threads between mapvtap helper and tun_fd in l_netns

    nsenter_shell(r_ns_pid)



if __name__=="__main__":
    #local()
    remote()
