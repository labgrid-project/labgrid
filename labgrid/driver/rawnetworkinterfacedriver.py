# pylint: disable=no-member
import contextlib
import json
import subprocess
import time
import os
import threading

import attr

from .common import Driver
from ..factory import target_factory
from ..step import step
from ..util.agentwrapper import AgentWrapper
from ..util.helper import processwrapper
from ..util.managedfile import ManagedFile
from ..util.timeout import Timeout
from ..resource.common import NetworkResource


def _get_nsenter_prefix(ns_pid):
    return ["nsenter", "-t", str(ns_pid), "-U", "-n", "-m", "--preserve-credentials"]


@target_factory.reg_driver
@attr.s(eq=False)
class RawNetworkInterfaceDriver(Driver):
    """RawNetworkInterface - Manage a network interface and interact with it at a low level

    Args:
        manage_interface (bool, default=True): if True this driver will
        setup/teardown the interface on activate/deactivate. Set this to False
        if you are managing the interface externally.
    """

    bindings = {
        "iface": {"NetworkInterface", "RemoteNetworkInterface", "USBNetworkInterface"},
    }
    manage_interface = attr.ib(default=True, validator=attr.validators.instance_of(bool))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._record_handle = None
        self._replay_handle = None
        self._remote_wrapper = None
        self._remote_netns = None
        self._remote_netns_pid = None
        self._remote_netns_prefix = None
        self._local_wrapper = None
        self._local_netns = None
        self._local_netns_pid = None
        self._local_netns_prefix = None

    def on_activate(self):
        if self.manage_interface:
            self._set_interface("up")
            self._wait_state("up")

    def on_deactivate(self):
        if self.manage_interface:
            self._set_interface("down")
            self._wait_state("down")

    def _wrap_command(self, args):
        wrapper = ["sudo", "labgrid-raw-interface"]

        if self.iface.command_prefix:
            # add ssh prefix, convert command passed via ssh (including wrapper) to single argument
            return self.iface.command_prefix + [" ".join(wrapper + args)]
        else:
            # keep wrapper and args as-is
            return wrapper + args

    @step(args=["state"])
    def _set_interface(self, state):
        """Set interface to given state."""
        cmd = ["ip", self.iface.ifname, state]
        cmd = self._wrap_command(cmd)
        subprocess.check_call(cmd)

    @Driver.check_active
    def set_interface_up(self):
        """Set bound interface up."""
        self._set_interface("up")

    @Driver.check_active
    def set_interface_down(self):
        """Set bound interface down."""
        self._set_interface("down")

    def _get_state(self):
        """Returns the bound interface's operstate."""
        if_state = self.iface.extra.get("state")
        if if_state:
            return if_state

        cmd = self.iface.command_prefix + ["cat", f"/sys/class/net/{self.iface.ifname}/operstate"]
        output = processwrapper.check_output(cmd).decode("ascii")
        if_state = output.strip()
        return if_state

    @Driver.check_active
    def get_state(self):
        """Returns the bound interface's operstate."""
        return self._get_state()

    @step(title="wait_state", args=["expected_state", "timeout"])
    def _wait_state(self, expected_state, timeout=60):
        """Wait until the expected state is reached or the timeout expires."""
        timeout = Timeout(float(timeout))

        while True:
            if self._get_state() == expected_state:
                return
            if timeout.expired:
                raise TimeoutError(
                    f"exported interface {self.iface.ifname} did not go {expected_state} within {timeout.timeout} seconds"
                )
            time.sleep(1)

    @Driver.check_active
    def wait_state(self, expected_state, timeout=60):
        """Wait until the expected state is reached or the timeout expires."""
        self._wait_state(expected_state, timeout=timeout)

    @Driver.check_active
    def get_ethtool_settings(self):
        """
        Returns settings via ethtool of the bound network interface resource.
        """
        cmd = self.iface.command_prefix + ["ethtool", "--json", self.iface.ifname]
        output = subprocess.check_output(cmd, encoding="utf-8")
        return json.loads(output)[0]

    @Driver.check_active
    @step(args=["settings"])
    def ethtool_configure(self, **settings):
        """
        Change settings on interface.

        Supported settings are described in ethtool(8) --change (use "_" instead of "-").
        """
        cmd = ["ethtool", "change", self.iface.ifname]
        cmd += [item.replace("_", "-") for pair in settings.items() for item in pair]
        cmd = self._wrap_command(cmd)
        subprocess.check_call(cmd)

    @Driver.check_active
    def get_ethtool_eee_settings(self):
        """
        Returns Energy-Efficient Ethernet settings via ethtool of the bound network interface
        resource.
        """
        cmd = self.iface.command_prefix + ["ethtool", "--show-eee", "--json", self.iface.ifname]
        output = subprocess.check_output(cmd, encoding="utf-8")
        return json.loads(output)[0]

    @Driver.check_active
    @step(args=["settings"])
    def ethtool_configure_eee(self, **settings):
        """
        Change Energy-Efficient Ethernet settings via ethtool of the bound network interface
        resource.

        Supported settings are described in ethtool(8) --set-eee (use "_" instead of "-").
        """
        cmd = ["ethtool", "set-eee", self.iface.ifname]
        cmd += [item.replace("_", "-") for pair in settings.items() for item in pair]
        cmd = self._wrap_command(cmd)
        subprocess.check_call(cmd)

    @Driver.check_active
    def get_ethtool_pause_settings(self):
        """
        Returns pause parameters via ethtool of the bound network interface resource.
        """
        cmd = self.iface.command_prefix + ["ethtool", "--json", "--show-pause", self.iface.ifname]
        output = subprocess.check_output(cmd, encoding="utf-8")
        return json.loads(output)[0]

    @Driver.check_active
    @step(args=["settings"])
    def ethtool_configure_pause(self, **settings):
        """
        Change pause parameters via ethtool of the bound network interface resource.

        Supported settings are described in ethtool(8) --pause
        """
        cmd = ["ethtool", "pause", self.iface.ifname]
        cmd += [item for pair in settings.items() for item in pair]
        cmd = self._wrap_command(cmd)
        subprocess.check_call(cmd)

    def _stop(self, proc, *, timeout=None):
        assert proc is not None

        try:
            _, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.terminate()
            _, err = proc.communicate()
            raise

        if proc.returncode:
            raise subprocess.CalledProcessError(
                returncode=proc.returncode,
                cmd=proc.args,
                stderr=err,
            )

    @Driver.check_active
    @step(args=["filename", "count", "timeout"])
    def start_record(self, filename, *, count=None, timeout=None):
        """
        Starts tcpdump on bound network interface resource.

        Args:
            filename (str): name of a file to record to, or None to record to stdout
            count (int): optional, exit after receiving this many number of packets
            timeout (int): optional, number of seconds to capture packets before tcpdump exits
        Returns:
            Popen object of tcpdump process
        """
        assert self._record_handle is None

        cmd = ["tcpdump", self.iface.ifname]
        if count is not None:
            cmd.append(str(count))
        if timeout is not None:
            cmd.append("--timeout")
            cmd.append(str(timeout))
        cmd = self._wrap_command(cmd)
        if filename is None:
            self._record_handle = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        else:
            with open(filename, "wb") as outdata:
                self._record_handle = subprocess.Popen(cmd, stdout=outdata, stderr=subprocess.PIPE)
        return self._record_handle

    @Driver.check_active
    @step(args=["timeout"])
    def stop_record(self, *, timeout=None):
        """
        Stops previously started tcpdump on bound network interface resource.

        Args:
            timeout (int): optional, maximum number of seconds to wait for the tcpdump process to
                           terminate
        """
        try:
            self._stop(self._record_handle, timeout=timeout)
        except subprocess.TimeoutExpired:
            # If live streaming packets, there is no reason to wait for tcpdump
            # to finish, so expect a timeout if piping to stdout
            if self._record_handle.stdout is None:
                raise
        finally:
            self._record_handle = None

    @contextlib.contextmanager
    def record(self, filename, *, count=None, timeout=None):
        """
        Context manager to start/stop tcpdump on bound network interface resource.

        Either count or timeout must be specified.

        Args:
            filename (str): name of a file to record to, or None to live stream packets
            count (int): optional, exit after receiving this many number of packets
            timeout (int): optional, number of seconds to capture packets before tcpdump exits
        Returns:
            Popen object of tcpdump process. If filename is None, packets can be read from stdout
        """
        assert count or timeout

        try:
            yield self.start_record(filename, count=count, timeout=timeout)
        finally:
            self.stop_record(timeout=0 if filename is None else None)

    @Driver.check_active
    @step(args=["filename"])
    def start_replay(self, filename):
        """
        Starts tcpreplay on bound network interface resource.

        Args:
            filename (str): name of a file to replay from
        Returns:
            Popen object of tcpreplay process
        """
        assert self._replay_handle is None

        if isinstance(self.iface, NetworkResource):
            mf = ManagedFile(filename, self.iface)
            mf.sync_to_resource()
            cmd = self._wrap_command([f"tcpreplay {self.iface.ifname} < {mf.get_remote_path()}"])
            self._replay_handle = subprocess.Popen(cmd, stderr=subprocess.PIPE)
        else:
            cmd = self._wrap_command(["tcpreplay", self.iface.ifname])
            with open(filename, "rb") as indata:
                self._replay_handle = subprocess.Popen(cmd, stdin=indata)

        return self._replay_handle

    @Driver.check_active
    @step(args=["timeout"])
    def stop_replay(self, *, timeout=None):
        """
        Stops previously started tcpreplay on bound network interface resource.

        Args:
            timeout (int): optional, maximum number of seconds to wait for the tcpreplay process to
                           terminate
        """
        try:
            self._stop(self._replay_handle, timeout=timeout)
        finally:
            self._replay_handle = None

    @contextlib.contextmanager
    def replay(self, filename, *, timeout=None):
        """
        Context manager to start/stop tcpreplay on bound network interface resource.

        Args:
            filename (str): name of a file to replay from
            timeout (int): optional, maximum number of seconds to wait for the tcpreplay process to
                           terminate
        """
        try:
            yield self.start_replay(filename)
        finally:
            self.stop_replay(timeout=timeout)

    @Driver.check_active
    @step()
    def get_statistics(self):
        """
        Returns basic interface statistics of bound network interface resource.
        """
        cmd = self.iface.command_prefix + ["ip", "--json", "-stats", "-stats", "link", "show", self.iface.ifname]
        output = processwrapper.check_output(cmd)
        return json.loads(output)[0]

    @Driver.check_active
    def get_address(self):
        """
        Returns the MAC address of the bound network interface resource.
        """
        return self.get_statistics()["address"]

    @Driver.check_active
    def _start_remote_netns(self):
        if self._remote_wrapper is not None:
            return

        self._remote_wrapper = AgentWrapper(self.iface.host)
        self._remote_netns = self._remote_wrapper.load('netns')
        self._remote_netns_pid = self._remote_netns.unshare()
        assert self._remote_netns_pid > 0

        self._remote_netns_prefix = self.iface.command_prefix + _get_nsenter_prefix(self._remote_netns_pid)

    @Driver.check_active
    def _start_local_netns(self):
        if self._local_wrapper is not None:
            return

        self._local_wrapper = AgentWrapper(None)
        self._local_netns = self._local_wrapper.load('netns')
        self._local_netns_pid = self._local_netns.unshare()
        assert self._local_netns_pid > 0

        self._local_netns_prefix = _get_nsenter_prefix(self._local_netns_pid)

    def _pump_d2p(self, dev, pipe):
        while True:
            buf = os.read(dev.fileno(), 1522)
            #print('Got tap data with length {}'.format(len(buf)))
            pipe.write(len(buf).to_bytes(2))
            pipe.write(buf)
            pipe.flush()

    def _pump_p2d(self, pipe, dev):
        while True:
            length = int.from_bytes(pipe.read(2))
            buf = pipe.read(length)
            #print('Got vtap data with length {}'.format(len(buf)))
            os.write(dev.fileno(), buf)

    def _start_pumps(self, dev, stdin, stdout):
        threading.Thread(target=self._pump_d2p, args=(dev, stdin), daemon=True).start()
        threading.Thread(target=self._pump_p2d, args=(stdout, dev), daemon=True).start()

    def setup_netns(self):
        self._start_remote_netns()
        self._start_local_netns()

        subprocess.check_call([
          "sudo",
          "/home/jluebbe/ptx/labgrid/helpers/labgrid-raw-interface",
          "ns-macvtap", self.iface.ifname, str(self._remote_netns_pid),
        ])

        links = self._remote_netns.get_links()
        r_macaddr = None
        for link in links:
            if link["ifname"] == "macvtap0":
                r_macaddr = link["address"]
        assert r_macaddr is not None

        # start mapvtap helper in r_ns
        helper = subprocess.Popen(
          [*self._remote_netns_prefix, 'labgrid-macvtap-fwd', 'macvtap0'],
           stdout = subprocess.PIPE, stdin = subprocess.PIPE,
        )

        tun_name, tun_fd = self._local_netns.create_tun(address=r_macaddr)

        links = self._local_netns.get_links()
        link_names = [link["ifname"] for link in links]
        assert "tap0" in link_names

        # start pump threads between mapvtap helper and tun_fd in self._local_netns
        self._start_pumps(tun_fd, helper.stdin, helper.stdout)

        with open("lg-remote-ns", "w") as f:
            prefix = self._remote_netns_prefix
            assert prefix[0] == "ssh"
            prefix = ["ssh", "-t"] + prefix[1:]
            f.write("\n".join([
                "#!/usr/bin/sh",
                " ".join(prefix),
                "",
            ]))
            os.fchmod(f.fileno(), 0o755)

        with open("lg-local-ns", "w") as f:
            f.write("\n".join([
                "#!/usr/bin/sh",
                " ".join(self._local_netns_prefix),
                "",
            ]))
            os.fchmod(f.fileno(), 0o755)
