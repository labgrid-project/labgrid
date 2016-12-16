import subprocess
import tempfile
import os
import time
import logging
import shutil
import atexit

import attr
from ..protocol import CommandProtocol, FileTransferProtocol
from ..resource import NetworkService
from ..factory import target_factory
from .exception import NoResourceError, ExecutionError, CleanUpError


@target_factory.reg_driver
@attr.s
class SSHDriver(CommandProtocol, FileTransferProtocol):
    """SSHDriver - Driver to execute commands via SSH"""
    target = attr.ib()

    def __attrs_post_init__(self):
        self.networkservice = self.target.get_resource(NetworkService) #pylint: disable=no-member,attribute-defined-outside-init
        if not self.networkservice:
            raise NoResourceError("Target has no {} Resource".format(NetworkService))
        self.target.drivers.append(self) #pylint: disable=no-member
        self.logger = logging.getLogger("{}({})".format(self, self.target))
        self.control = self._check_master()

    def _start_own_master(self):
        """Starts a controlmaster connection in a temporary directory."""
        self.tmpdir = tempfile.mkdtemp(prefix='labgrid-ssh-tmp-')
        control = os.path.join(self.tmpdir, 'control-{}'.format(self.networkservice.address))
        args = ["ssh","-f", "-x", "-o", "ControlPersist=300", "-o", "PasswordAuthentication=no", "-o", "StrictHostKeyChecking=no", "-MN", "-S", control, '{}@{}'.format(self.networkservice.username, self.networkservice.address)]
        self.process = subprocess.Popen(
            args,
        )

        if self.process.wait(timeout=1) is not 0:
            raise ExecutionError("failed to connect to {} with {} and {}".format(self.networkservice.address, args, self.process.wait()))

        if not os.path.exists(control):
            raise ExecutionError("no control socket to {}".format(self.networkservice.address))

        self.logger.debug('Connected to {}'.format(self.networkservice.address))

        atexit.register(self._cleanup_own_master)

        return control


    def _check_master(self):
        args = ["ssh", "-O", "check", "{}@{}".format(self.networkservice.username, self.networkservice.address)]
        # FIXME: API change in python3.5 call -> run
        check = subprocess.call(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if check == 0:
            return ""
        else:
            return self._start_own_master()

    def run(self, cmd):
        """Execute `cmd` on the target.

        This method runs the specified `cmd` as a command on its target.
        It uses the ssh shell command to run the command and parses the exitcode.
        cmd - command to be run on the target

        returns:
        (stdout, stderr, returncode)
        """
        if self.control:
            complete_cmd = "ssh -x -o ControlPath={cpath} {user}@{host} {cmd}".format(cpath=self.control,user=self.networkservice.username,
                                                                                      host=self.networkservice.address,
                                                                                      cmd=cmd).split(' ')
        else:
            complete_cmd = "ssh -x {user}@{host} {cmd}".format(user=self.networkservice.username,
                                                               host=self.networkservice.address,
                                                               cmd=cmd).split(' ')
        self.logger.debug("Sending command: %s", complete_cmd)
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

    def put(self, filename, remotepath=None):
        if self.control:
            transfer_cmd = "scp -o ControlPath={cpath} {filename} {user}@{host}:{remotepath}".format(cpath=self.control,
                                                                                                     filename=filename,
                                                                                                     user=self.networkservice.username,
                                                                                                     host=self.networkservice.address,
                                                                                                     remotepath=remotepath).split(' ')
        else:
            transfer_cmd = "scp {filename} {user}@{host}:{remotepath}".format(filename=filename,
                                                                              user=self.networkservice.username,
                                                                              host=self.networkservice.address,
                                                                              remotepath=remotepath).split(' ')
        try:
            # FIXME: API change in python3.5 call -> run
            sub = subprocess.call(transfer_cmd)#, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            raise ExecutionError("error executing command: {}".format(transfer_cmd))
        if sub is not 0:
            raise ExecutionError("error executing command: {}".format(transfer_cmd))

    def get(self, filename):
        if self.control:
            transfer_cmd = "scp -o ControlPath={cpath} {user}@{host}:{filename} .".format(cpath=self.control,
                                                                                        filename=filename,
                                                                                        user=self.networkservice.username,
                                                                                        host=self.networkservice.address).split(' ')
        else:
            transfer_cmd = "scp {user}@{host}:{filename} .".format(filename=filename,
                                                                 user=self.networkservice.username,
                                                                 host=self.networkservice.address).split(' ')
        try:
            # FIXME: API change in python3.5 call -> run
            sub = subprocess.call(transfer_cmd)#, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            raise ExecutionError("error executing command: {}".format(transfer_cmd))
        if sub is not 0:
            raise ExecutionError("error executing command: {}".format(transfer_cmd))

    def _cleanup_own_master(self):
        complete_cmd = "ssh -x -o ControlPath={cpath} -O exit {user}@{host}".format(cpath=self.control,user=self.networkservice.username,
                                                         host=self.networkservice.address).split(' ')
        # FIXME: API change in python3.5 call -> run
        res = subprocess.call(complete_cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        if res !=0:
            raise CleanUpError("Could not cleanup ControlMaster")
        shutil.rmtree(self.tmpdir)
