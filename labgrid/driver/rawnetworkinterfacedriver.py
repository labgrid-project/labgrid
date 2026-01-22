# pylint: disable=no-member
import contextlib
import json
import subprocess
import time
import os
import functools
import logging
import socket
import tempfile
import sys

import attr

from .common import Driver
from .exception import ExecutionError
from ..factory import target_factory
from ..step import step
from ..util.agentwrapper import AgentWrapper
from ..util.helper import processwrapper
from ..util.managedfile import ManagedFile
from ..util.timeout import Timeout
from ..resource.common import NetworkResource


class NetNamespace(object):
    def __init__(self, agent):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._agent = agent

    @functools.cached_property
    def prefix(self):
        return self._agent.get_prefix()

    @functools.cached_property
    def intf(self):
        return self._agent.get_intf()

    def _get_cmd(self, command):
        if isinstance(command, str):
            return self.prefix + ["--wd=" + os.getcwd(), "--", "/bin/sh", "-c", command]
        return self.prefix + ["--wd=" + os.getcwd(), "--"] + command

    def run(self, command, **kwargs):
        cmd = self._get_cmd(command)
        self.logger.debug("Running %s", cmd)
        return subprocess.run(cmd, **kwargs)

    def Popen(self, command, **kwargs):
        cmd = self._get_cmd(command)
        self.logger.debug("Popen %s", cmd)
        return subprocess.Popen(cmd, **kwargs)

    @contextlib.contextmanager
    def _create_script(self, script):
        with tempfile.NamedTemporaryFile("w") as s:
            s.write(script)
            s.flush()

            yield [sys.executable, s.name]

    def run_script(self, script, script_args=[], **kwargs):
        with self._create_script(script) as command:
            return self.run(command + script_args, **kwargs)

    @contextlib.contextmanager
    def Popen_script(self, script, script_args=[], **kwargs):
        with self._create_script(script) as command:
            with self.Popen(command + script_args, **kwargs) as p:
                yield p

    def socket(self, *args, **kwargs):
        err, fd = self._agent.create_socket(*args, **kwargs)
        if err:
            raise OSError(err, os.strerror(err))
        return socket.socket(fileno=fd)

    def connect(self, address, port, *args, **kwargs):
        err, fd = self._agent.connect(address, port, *args, **kwargs)
        if err:
            raise OSError(err, os.strerror(err))
        return socket.socket(fileno=fd)

    def bind(self, host, port, *args, **kwargs):
        err, fd = self._agent.bind(host, port, *args, **kwargs)
        if err:
            raise OSError(err, os.strerror(err))
        return socket.socket(fileno=fd)


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
    @contextlib.contextmanager
    def _netns(self, host):
        with AgentWrapper(host) as wrapper:
            ns = wrapper.load("netns")
            ns.unshare()
            yield ns

    @contextlib.contextmanager
    def setup_netns(self, mac_address=None):
        with contextlib.ExitStack() as ctx:
            remote_ns = ctx.enter_context(self._netns(self.iface.host))
            local_ns = ctx.enter_context(self._netns(None))

            cmd = [
                "-d",
                "ns-macvtap",
                self.iface.ifname,
                str(remote_ns.get_pid()),
            ]
            if mac_address:
                cmd.append("--mac-address")
                cmd.append(mac_address)

            # Start tap forward in remote namespace
            remote_fwd = ctx.enter_context(
                subprocess.Popen(
                    self._wrap_command(cmd),
                    stdout=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                )
            )
            ctx.callback(lambda: remote_fwd.terminate())

            r_macaddr = None
            to = Timeout(30.0)
            while True:
                if to.expired:
                    raise TimeoutError("Timeout waiting for remote macvtap to be established")

                links = remote_ns.get_links()
                for link in links:
                    if link["ifname"] == "macvtap0":
                        r_macaddr = link["address"]
                        break

                if r_macaddr is not None:
                    break

                if remote_fwd.poll() is not None:
                    raise ExecutionError(f"Remote tap forward {remote_fwd.pid} died with {remote_fwd.returncode}")

                time.sleep(0.1)

            _, fd = local_ns.create_tun(address=r_macaddr)
            tun_fd = ctx.enter_context(os.fdopen(fd))

            links = local_ns.get_links()
            link_names = [link["ifname"] for link in links]
            assert "tap0" in link_names

            local_fwd = ctx.enter_context(
                subprocess.Popen(
                    local_ns.get_prefix() + ["labgrid-tap-fwd", str(tun_fd.fileno())],
                    stdin=remote_fwd.stdout,
                    stdout=remote_fwd.stdin,
                    pass_fds=(tun_fd.fileno(),),
                )
            )
            ctx.callback(lambda: local_fwd.terminate())

            # Close local pipes for the remote forward, now that the local forward is running
            remote_fwd.stdin.close()
            remote_fwd.stdout.close()

            ns = NetNamespace(local_ns)

            # Wait for IPv6 address negotiation to finish
            to = Timeout(30.0)
            while True:
                if to.expired:
                    raise TimeoutError("Timeout waiting for IPv6 address negotiation to finish")

                data = json.loads(
                    ns.run(["ip", "-j", "addr", "show", "dev", ns.intf], check=True, stdout=subprocess.PIPE).stdout
                )
                for addr in data[0].get("addr_info", []):
                    if addr.get("tentative", False):
                        break
                else:
                    # No tentative addresses
                    break

                if remote_fwd.poll() is not None:
                    raise ExecutionError(f"Remote tap forward {remote_fwd.pid} died with {remote_fwd.returncode}")

                if local_fwd.poll() is not None:
                    raise ExecutionError(f"Local tap forward {local_fwd.pid} died with {local_fwd.returncode}")

                time.sleep(0.1)

            yield ns
