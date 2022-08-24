import attr

from ..factory import target_factory
from .common import Driver
from ..protocol import DynamicNetworkServiceProtocol
from ..util.helper import get_free_port


@target_factory.reg_driver
@attr.s(eq=False)
class QEMUNetworkService(Driver, DynamicNetworkServiceProtocol):
    """
    The QEMUNetworkService implements an interface that describe a network
    service on a QEMU instance. If QEMU is configured to do SLiRP ("user")
    networking, the service will be proxied to an ephemeral port on localhost
    and the NetworkService created by this driver will reflect that

    Args:
        address (str): the IP address of the service
        username (str): the username used to login to the service
        password (str): optional, the password used to login to the service
        port (int, default=22): optional, the port number of the service
    """

    bindings = {
        "qemu": "QEMUDriver",
    }

    address = attr.ib(validator=attr.validators.instance_of(str))
    username = attr.ib(validator=attr.validators.instance_of(str))
    password = attr.ib(default="", validator=attr.validators.instance_of(str))
    port = attr.ib(default=22, validator=attr.validators.instance_of(int))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._networkservice = None
        self._forward = None

    def on_activate(self):
        if self._networkservice:
            self._activate_service()

    def on_deactivate(self):
        self.qemu.remove_port_forward(
            "tcp",
            self._networkservice.address,
            self._networkservice.port,
        )
        self.target.deactivate(self._networkservice)

    def _activate_service(self):
        self.qemu.add_port_forward(
            "tcp",
            self._networkservice.address,
            self._networkservice.port,
            self._networkservice.extra["remote_address"],
            self._networkservice.extra["remote_port"],
        )
        self.target.activate(self._networkservice)

    @Driver.check_active
    def get_network_service(self):
        if self._networkservice:
            return self._networkservice

        if "user" in self.qemu.nic.split(","):
            local_port = get_free_port()

            params = {
                "address": "127.0.0.1",
                "username": self.username,
                "password": self.password,
                "port": local_port,
            }
            extra = {
                "never_proxy": True,
            }
        else:
            params = {
                "address": self.address,
                "username": self.username,
                "password": self.password,
                "port": self.port,
            }
            extra = {}

        self._networkservice = target_factory.make_resource(
            self.target,
            "NetworkService",
            self.name,
            params,
        )
        self._networkservice.extra = {
            **extra,
            "remote_address": self.address,
            "remote_port": self.port,
        }

        self._activate_service()
        return self._networkservice
