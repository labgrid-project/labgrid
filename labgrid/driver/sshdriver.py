import attr
from ..protocol import CommandProtocol, FilesystemProtocol
from ..resource import NetworkService
from ..factory import target_factory
from .exception import NoResourceError


@target_factory.reg_driver
@attr.s
class SSHDriver(CommandProtocol, FilesystemProtocol):
    """SSHDriver - Driver to execute commands via SSH"""
    target = attr.ib()

    def __attrs_post_init__(self):
        # FIXME: Hard coded for only one driver, should find the correct one in order
        self.networkservice = self.target.get_resource(NetworkService) #pylint: disable=no-member,attribute-defined-outside-init
        if not self.networkservice:
            raise NoResourceError("Target has no {} Resource".format(NetworkService))
        self.target.drivers.append(self) #pylint: disable=no-member

    def run(self, cmd):
        pass
    def run_check(self, cmd):
        """
        Runs the specified cmd on the shell and returns the output if successful,
        raises ExecutionError otherwise.

        Arguments:
        cmd - cmd to run on the shell
        """
        res = self.run(cmd)
        if res[1] != 0:
            raise ExecutionError(cmd)

    def get_status(self):
        pass

    def put(self, filename):
        pass

    def get(self, filename):
        pass
