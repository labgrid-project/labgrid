import subprocess

import attr
from ..protocol import CommandProtocol, FilesystemProtocol
from ..resource import NetworkService
from ..factory import target_factory
from .exception import NoResourceError, ExecutionError


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
        complete_cmd = "ssh -x -o PasswordAuthentication=no -o StrictHostKeyChecking=no {user}@{host} {cmd}".format(user=self.networkservice.username,
                                                                                                                    host=self.networkservice.address,
                                                                                                                    cmd=cmd).split(' ')
        try:
            sub = subprocess.Popen(complete_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except:
            raise ExecutionError("error executing command: {}".format(complete_cmd))

        stdout, stderr = sub.communicate()
        if sub.returncode != 0:
            raise ExecutionError("Error executing remote command: {}, output {}/{}".format(complete_cmd, stdout,stderr))
        res = stdout.decode("utf-8").split('\n')
        res.pop()
        return (res, sub.returncode)

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
        return res[0]

    def get_status(self):
        return 1

    def put(self, filename):
        pass

    def get(self, filename):
        pass
