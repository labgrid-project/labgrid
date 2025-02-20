import contextlib

import attr

from .common import Driver
from .exception import ExecutionError
from ..factory import target_factory
from ..step import step
from ..util.agentwrapper import AgentWrapper
from ..util.ssh import sshmanager
from ..resource.remote import RemoteNetworkInterface


@target_factory.reg_driver
@attr.s(eq=False)
class NetworkInterfaceDriver(Driver):
    bindings = {
        "iface": {"RemoteNetworkInterface", "NetworkInterface", "USBNetworkInterface"},
    }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.wrapper = None

    def on_activate(self):
        if isinstance(self.iface, RemoteNetworkInterface):
            host = self.iface.host
            self.ssh = sshmanager.get(host)
        else:
            host = None
            # port forwarding is not useful for localhost
            self.ssh = None
        self.wrapper = AgentWrapper(host)
        self.proxy = self.wrapper.load('network_interface')

    def on_deactivate(self):
        try:
            self.proxy.disable(self.iface.ifname)
        finally:
            self.wrapper.close()
            self.wrapper = None
            self.proxy = None

    @property
    def skip_deactivate_on_export(self):
        # We need to keep the agent and SSH exports active.
        return True

    def get_export_vars(self):
        return {
            "host": self.iface.host,
            "ifname": self.iface.ifname or "",
        }

    # basic
    @Driver.check_active
    @step()
    def configure(self, settings):
        "Set a configuration on this interface and activate it."
        self.proxy.configure(self.iface.ifname, settings)

    @Driver.check_active
    @step(args=["expected"])
    def wait_state(self, expected, timeout=60):
        """Wait until the expected state is reached or the timeout expires.

        Possible states include disconnected and activated. See NM's
        DeviceState for more details.
        """
        self.proxy.wait_state(self.iface.ifname, expected, timeout)

    @Driver.check_active
    @step()
    def disable(self):
        "Disable and remove the created labgrid connection."
        self.proxy.disable(self.iface.ifname)

    @Driver.check_active
    @step()
    def get_active_settings(self):
        "Get the currently active settings from this interface."
        return self.proxy.get_active_settings(self.iface.ifname)

    @Driver.check_active
    @step()
    def get_settings(self):
        "Get the settings of the labgrid connection for this interface."
        return self.proxy.get_settings(self.iface.ifname)

    @Driver.check_active
    @step()
    def get_state(self):
        """Get the current state of this interface.

        This includes information such as the addresses or WiFi connection.
        """
        return self.proxy.get_state(self.iface.ifname)

    # dhcpd
    @Driver.check_active
    @step()
    def get_dhcpd_leases(self):
        """Get the list of active DHCP leases in shared mode.

        This requires read access to /var/lib/NetworkManager/dnsmasq-* on the
        exporter.
        """

        return self.proxy.get_dhcpd_leases(self.iface.ifname)

    # wireless
    @Driver.check_active
    @step()
    def request_scan(self):
        "Request a scan to update the list visible access points."
        return self.proxy.request_scan(self.iface.ifname)

    @Driver.check_active
    @step()
    def get_access_points(self, scan=None):
        """Get the list of currently visible access points.

        When scan is None (the default), it will automatically trigger a scan
        if the last scan is more than 30 seconds old.
        """
        return self.proxy.get_access_points(self.iface.ifname, scan)

    @Driver.check_active
    @contextlib.contextmanager
    def forward_local(self, remote_host, remote_port, local_port=None):
        """Forward a local port to an address and port via the exporter.

        A context manager that keeps the local port forwarded as long as the
        context remains valid. A connection can be made to the returned port on
        localhost and it will be forwarded to the address and port.

        If localport is not set, a random free port will be selected.

        usage:
            with netif.forward_local('127.0.0.1', 8080, local_port=1234) as local_port:
                # Use localhost:1234 here to connect to port 8080 on
                # the exporter

            with netif.forward_local('192.168.1.2', 8080) as local_port:
                # Use localhost:local_port here to connect to port 8080 on
                # 192.168.1.2

        returns:
            local_port
        """
        if not self.ssh:
            raise ExecutionError("Resource is not on an exporter")

        local_port = self.ssh.add_port_forward(remote_host, remote_port, local_port)
        try:
            yield local_port
        finally:
            self.ssh.remove_port_forward(remote_host, remote_port)

    @Driver.check_active
    @contextlib.contextmanager
    def forward_remote(self, remote_port, local_port, remote_bind=None):
        """Forward a remote port on the exporter to a local port.

        A context manager that keeps a remote port forwarded to a local port as
        long as the context remains valid. A connection can be made to the
        remote port on the target device will be forwarded to the returned local
        port on localhost.

        Note that the remote socket is not *bound* to any specific IP by
        default, making it reachable by the target. Also, 'GatewayPorts
        clientspecified' needs to be configured in the remote host's
        sshd_config.

        usage:
            with netif.forward_remote(8080, 8081) as local_port:
                # Connections to port 8080 on the exporter will be redirected to
                # localhost:8081
        """
        if not self.ssh:
            raise ExecutionError("Resource is not on an exporter")

        self.ssh.add_remote_port_forward(remote_port, local_port, remote_bind)
        try:
            yield
        finally:
            self.ssh.remove_remote_port_forward(remote_port, local_port, remote_bind)
