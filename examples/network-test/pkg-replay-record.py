#!/usr/bin/env python3
# Generates an Ethernet frame via scapy using pcap, copies pcap to DUT, replays pcap on interface,
# records frame locally (or on exporter, adjust env.yaml accordingly), and compares both.

import logging
import os
from tempfile import NamedTemporaryFile, TemporaryDirectory

from scapy.all import Ether, Raw, rdpcap, wrpcap, conf

from labgrid import Environment
from labgrid.logging import basicConfig, StepLogger


def generate_frame():
    frame = Ether(dst="11:22:33:44:55:66", src="66:55:44:33:22:11", type=0x9000)
    padding = "\x00" * (conf.min_pkt_size - len(frame))
    frame /= Raw(load=padding)
    return frame


basicConfig(level=logging.INFO)
StepLogger.start()
env = Environment("env.yaml")
target = env.get_target()

netdrv = target.get_driver("RawNetworkInterfaceDriver")
ssh = target.get_driver("SSHDriver")

# get DUT interface
exporter_iface = netdrv.iface.ifname
dut_iface = env.config.get_target_option(target.name, "local_iface_to_dut_iface")[exporter_iface]

# generate test frame
generated_frame = generate_frame()

# write pcap, copy to DUT
remote_pcap = "/tmp/pcap"
with NamedTemporaryFile() as pcap:
    wrpcap(pcap.name, generated_frame)
    ssh.put(pcap.name, remote_pcap)

# copy recorded pcap from DUT, compare with generated frame
with TemporaryDirectory() as tempdir:
    # start record on exporter
    tempf = os.path.join(tempdir, "record.pcap")
    with netdrv.record(tempf, count=1) as record:
        # replay pcap on DUT
        ssh.run_check(f"ip link set {dut_iface} up")
        ssh.run_check(f"tcpreplay -i {dut_iface} {remote_pcap}")

    remote_frame = rdpcap(tempf)
    assert remote_frame[0] == generated_frame[0]

print("statistics", netdrv.get_statistics())
print("address", netdrv.get_address())
