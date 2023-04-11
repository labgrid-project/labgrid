from importlib import import_module
import socket
import attr

from ..factory import target_factory
from ..resource.remote import NetworkJLinkDevice
from ..util.proxy import proxymanager
from .common import Driver

@target_factory.reg_driver
@attr.s(eq=False)
class JLinkDriver(Driver):
    bindings = {"jlink_device": {"JLinkDevice", "NetworkJLinkDevice"}, }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._module = import_module('pylink')
        self.jlink = None

    def on_activate(self):
        self.jlink = self._module.JLink()

        if isinstance(self.jlink_device, NetworkJLinkDevice):
            # we can only forward if the backend knows which port to use
            host, port = proxymanager.get_host_and_port(self.jlink_device)
            # The J-Link client software does not support host names
            ip_addr = socket.gethostbyname(host)

            # Workaround for Debian's /etc/hosts entry
            # https://www.debian.org/doc/manuals/debian-reference/ch05.en.html#_the_hostname_resolution
            if ip_addr == "127.0.1.1":
                ip_addr = "127.0.0.1"
            self.jlink.open(ip_addr=f"{ip_addr}:{port}")
        else:
            self.jlink.open(serial_no=self.jlink_device.serial)

    def on_deactivate(self):
        self.jlink.close()
        self.jlink = None

    @Driver.check_active
    def get_interface(self):
        return self.jlink
