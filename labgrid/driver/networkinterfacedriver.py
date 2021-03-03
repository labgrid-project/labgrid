# pylint: disable=no-member
import attr

from .common import Driver
from ..factory import target_factory
from ..step import step
from ..util.agentwrapper import AgentWrapper
from ..resource.remote import RemoteNetworkInterface


@target_factory.reg_driver
@attr.s(eq=False)
class NetworkInterfaceDriver(Driver):
    bindings = {
        "iface": {"RemoteNetworkInterface", "USBNetworkInterface"},
    }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.wrapper = None

    def on_activate(self):
        if isinstance(self.iface, RemoteNetworkInterface):
            host = self.iface.host
        else:
            host = None
        self.wrapper = AgentWrapper(host)
        self.proxy = self.wrapper.load('network_interface')

    def on_deactivate(self):
        try:
            self.proxy.disable(self.iface.ifname)
        finally:
            self.wrapper.close()
            self.wrapper = None
            self.proxy = None

    # basic
    @Driver.check_active
    @step()
    def configure(self, settings):
        "Set a configuration on this interface and activate it."
        self.proxy.configure(self.iface.ifname, settings)

    @Driver.check_active
    @step()
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
