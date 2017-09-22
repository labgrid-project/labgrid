# pylint: disable=no-member
"""The SSHDriver uses SSH as a transport to implement CommandProtocol and FileTransferProtocol"""
import logging
import os
import sys
import shutil
import subprocess
import tempfile

import attr

from ..factory import target_factory
from ..protocol import CommandProtocol, FileTransferProtocol, InfoProtocol
from ..resource import NetworkService
from .commandmixin import CommandMixin
from ..util import Timeout
from .common import Driver
from ..step import step
from .exception import CleanUpError, ExecutionError


@target_factory.reg_driver
@attr.s(cmp=False)
class SSHDriver(CommandMixin, Driver, CommandProtocol, FileTransferProtocol):
    """SSHDriver - Driver to execute commands via SSH"""
    bindings = {"networkservice": NetworkService, }
    keyfile = attr.ib(default="", validator=attr.validators.instance_of(str))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.logger = logging.getLogger("{}({})".format(self, self.target))

    def on_activate(self):
        self.ssh_prefix = "-i {}".format(os.path.abspath(self.keyfile)
                                         ) if self.keyfile else ""
        self.ssh_prefix += " -o LogLevel=ERROR"
        self.control = self._check_master()
        self.ssh_prefix += " -F /dev/null"
        self.ssh_prefix += " -o ControlPath={}".format(
            self.control
        ) if self.control else ""

    def on_deactivate(self):
        self._cleanup_own_master()

    def _start_own_master(self):
        """Starts a controlmaster connection in a temporary directory."""
        self.tmpdir = tempfile.mkdtemp(prefix='labgrid-ssh-tmp-')
        control = os.path.join(
            self.tmpdir, 'control-{}'.format(self.networkservice.address)
        )
        args = "ssh -f {} -x -o ConnectTimeout=30 -o ControlPersist=300 -o PasswordAuthentication=no -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -MN -S {} {}@{}".format(
            self.ssh_prefix, control, self.networkservice.username,
            self.networkservice.address
        ).split(" ")
        self.process = subprocess.Popen(args, )

        try:
            if self.process.wait(timeout=30) is not 0:
                raise ExecutionError(
                    "failed to connect to {} with {} and {}".
                    format(self.networkservice.address, args, self.process.wait())
                )
        except TimeoutExpired:
                raise ExecutionError(
                    "failed to connect to {} with {} and {}".
                    format(self.networkservice.address, args, self.process.wait())
                )

        if not os.path.exists(control):
            raise ExecutionError(
                "no control socket to {}".format(self.networkservice.address)
            )

        self.logger.debug('Connected to %s', self.networkservice.address)

        return control

    def _check_master(self):
        args = [
            "ssh", "-O", "check", "{}@{}".format(
                self.networkservice.username, self.networkservice.address
            )
        ]
        check = subprocess.call(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        if check == 0:
            return ""
        else:
            return self._start_own_master()

    @Driver.check_active
    @step(args=['cmd'])
    def run(self, cmd, print=False):
        """Execute `cmd` on the target.

        This method runs the specified `cmd` as a command on its target.
        It uses the ssh shell command to run the command and parses the exitcode.
        cmd - command to be run on the target

        returns:
        (stdout, stderr, returncode)
        """
        complete_cmd = "ssh -x {prefix} {user}@{host} {cmd}".format(
            user=self.networkservice.username,
            host=self.networkservice.address,
            cmd=cmd,
            prefix=self.ssh_prefix
        ).split(' ')
        self.logger.debug("Sending command: %s", complete_cmd)
        try:
            sub = subprocess.Popen(
                complete_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
        except:
            raise ExecutionError(
                "error executing command: {}".format(complete_cmd)
            )

        stdout, stderr = sub.communicate()
        stdout = stdout.decode("utf-8").split('\n')
        stderr = stderr.decode("utf-8").split('\n')
        stdout.pop()
        stderr.pop()
        if print:
            sys.stdout.write("\n".join(stdout))
            sys.stderr.write("\n".join(stderr))
        return (stdout, stderr, sub.returncode)

    @Driver.check_active
    @step(args=['cmd'])
    def run_check(self, cmd, print=False):
        """
        Runs the specified cmd on the shell and returns the output if successful,
        raises ExecutionError otherwise.

        Arguments:
        cmd - cmd to run on the shell
        """
        res = self.run(cmd,print=print)
        if res[2] != 0:
            raise ExecutionError(cmd)
        return res[0]

    def get_status(self):
        """The SSHDriver is always connected, return 1"""
        return 1

    @Driver.check_active
    @step(args=['filename', 'remotepath'])
    def put(self, filename, remotepath=None):
        transfer_cmd = "scp {prefix} {filename} {user}@{host}:{remotepath}".format(
            filename=filename,
            user=self.networkservice.username,
            host=self.networkservice.address,
            remotepath=remotepath,
            prefix=self.ssh_prefix
        ).split(' ')
        try:
            sub = subprocess.call(
                transfer_cmd
            )  #, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            raise ExecutionError(
                "error executing command: {}".format(transfer_cmd)
            )
        if sub is not 0:
            raise ExecutionError(
                "error executing command: {}".format(transfer_cmd)
            )

    @Driver.check_active
    @step(args=['filename', 'destination'])
    def get(self, filename, destination="."):
        transfer_cmd = "scp {prefix} {user}@{host}:{filename} {destination}".format(
            filename=filename,
            user=self.networkservice.username,
            host=self.networkservice.address,
            prefix=self.ssh_prefix,
            destination=destination
        ).split(' ')
        try:
            sub = subprocess.call(
                transfer_cmd
            )  #, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            raise ExecutionError(
                "error executing command: {}".format(transfer_cmd)
            )
        if sub is not 0:
            raise ExecutionError(
                "error executing command: {}".format(transfer_cmd)
            )

    def _cleanup_own_master(self):
        """Exit the controlmaster and delete the tmpdir"""
        complete_cmd = "ssh -x -o ControlPath={cpath} -O exit {user}@{host}".format(
            cpath=self.control,
            user=self.networkservice.username,
            host=self.networkservice.address
        ).split(' ')
        res = subprocess.call(
            complete_cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        if res != 0:
            self.logger.info("Socket already closed")
        shutil.rmtree(self.tmpdir)
