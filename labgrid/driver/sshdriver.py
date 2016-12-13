import attr
from ..protocol import CommandProtocol, FilesystemProtocol
from ..resource import NetworkService
from .exception import NoResourceException


@attr.s
class SSHDriver(CommandProtocol, FilesystemProtocol):
    """SSHDriver - Driver to execute commands via SSH"""
    target = attr.ib()

    def __attrs_post_init__(self):
        # FIXME: Hard coded for only one driver, should find the correct one in order
        self.networkservice = self.target.get_resource(NetworkService) #pylint: disable=no-member,attribute-defined-outside-init
        if not self.networkservice:
            raise NoResourceException("Target has no {} Resource".format(NetworkService))
        self.target.drivers.append(self) #pylint: disable=no-member

    def run(self, cmd):
        pass

    def get_status(self):
        pass

    def upload(self, filename):
        pass

    def download(self, filename):
        pass
