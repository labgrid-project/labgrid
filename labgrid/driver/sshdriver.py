import subprocess
import tempfile
import logging
import shutil
import atexit

import attr
from ..protocol import CommandProtocol, FileTransferProtocol
from ..resource import NetworkService
from ..factory import target_factory
from .exception import NoResourceError, ExecutionError


@target_factory.reg_driver
@attr.s
class SSHDriver(CommandProtocol, FileTransferProtocol):
    """SSHDriver - Driver to execute commands via SSH"""
    target = attr.ib()

    def __attrs_post_init__(self):
        # FIXME: Hard coded for only one driver, should find the correct one in order
        self.networkservice = self.target.get_resource(NetworkService) #pylint: disable=no-member,attribute-defined-outside-init
        if not self.networkservice:
            raise NoResourceError("Target has no {} Resource".format(NetworkService))
        self.target.drivers.append(self) #pylint: disable=no-member
        self.tmpdir = tempfile.mkdtemp(prefix='labgrid-ssh-tmp-')
        atexit.register(self._cleanup)
        self.logger = logging.getLogger("{}({})".format(self, self.target))

    def run(self, cmd):
        """Execute `cmd` on the target.

        This method runs the specified `cmd` as a command on its target.
        It uses the ssh shell command to run the command and parses the exitcode.
        cmd - command to be run on the target

        returns:
        (stdout, stderr, returncode)
        """
        complete_cmd = "ssh -x -o PasswordAuthentication=no -o StrictHostKeyChecking=no {user}@{host} {cmd}".format(user=self.networkservice.username,
                                                                                                                    host=self.networkservice.address,
                                                                                                                    cmd=cmd).split(' ')
        try:
            sub = subprocess.Popen(complete_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except:
            raise ExecutionError("error executing command: {}".format(complete_cmd))

        stdout, stderr = sub.communicate()
        stdout = stdout.decode("utf-8").split('\n')
        stderr = stderr.decode("utf-8").split('\n')
        stdout.pop()
        stderr.pop()
        return (stdout, stderr, sub.returncode)

    def run_check(self, cmd):
        """
        Runs the specified cmd on the shell and returns the output if successful,
        raises ExecutionError otherwise.

        Arguments:
        cmd - cmd to run on the shell
        """
        res = self.run(cmd)
        if res[2] != 0:
            raise ExecutionError(cmd)
        return res[0]

    def get_status(self):
        """The SSHDriver is always connected, return 1"""
        return 1

    def put(self, filename):
        pass

    def get(self, filename):
        pass

    def _cleanup(self):
        shutil.rmtree(self.tmpdir)
