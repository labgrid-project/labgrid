# pylint: disable=no-member
"""The SSHDriver uses SSH as a transport to implement CommandProtocol and FileTransferProtocol"""
import logging
import os
import shutil
import subprocess
import tempfile

import attr

from ..factory import target_factory
from ..protocol import CommandProtocol, FileTransferProtocol
from ..resource import NetworkService
from .commandmixin import CommandMixin
from .common import Driver
from ..step import step
from .exception import ExecutionError


@target_factory.reg_driver
@attr.s(eq=False)
class SSHDriver(CommandMixin, Driver, CommandProtocol, FileTransferProtocol):
    """SSHDriver - Driver to execute commands via SSH"""
    bindings = {"networkservice": NetworkService, }
    priorities = {CommandProtocol: 10, FileTransferProtocol: 10}
    keyfile = attr.ib(default="", validator=attr.validators.instance_of(str))
    stderr_merge = attr.ib(default=False, validator=attr.validators.instance_of(bool))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.logger = logging.getLogger("{}({})".format(self, self.target))

    def on_activate(self):
        self.ssh_prefix = "-o LogLevel=ERROR"
        if self.keyfile:
            keyfile_path = self.keyfile
            if self.target.env:
                keyfile_path = self.target.env.config.resolve_path(self.keyfile)
            self.ssh_prefix += " -i {}".format(keyfile_path)
        self.ssh_prefix += " -o PasswordAuthentication=no" if (
            not self.networkservice.password) else ""
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
        # use sshpass if we have a password
        sshpass = "sshpass -e " if self.networkservice.password else ""
        args = ("{}ssh -f {} -x -o ConnectTimeout=30 -o ControlPersist=300 -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o ServerAliveInterval=15 -MN -S {} -p {} {}@{}").format( # pylint: disable=line-too-long
            sshpass, self.ssh_prefix, control, self.networkservice.port,
            self.networkservice.username, self.networkservice.address).split(" ")

        env = os.environ.copy()
        if self.networkservice.password:
            env['SSHPASS'] = self.networkservice.password
        self.process = subprocess.Popen(args, env=env)

        try:
            if self.process.wait(timeout=30) != 0:
                raise ExecutionError(
                    "failed to connect to {} with {} and {}".
                    format(self.networkservice.address, args, self.process.wait())
                )
        except subprocess.TimeoutExpired:
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

        return self._start_own_master()

    @Driver.check_active
    @step(args=['cmd'], result=True)
    def run(self, cmd, codec="utf-8", decodeerrors="strict", timeout=None): # pylint: disable=unused-argument
        return self._run(cmd, codec=codec, decodeerrors=decodeerrors)

    def _run(self, cmd, codec="utf-8", decodeerrors="strict", timeout=None): # pylint: disable=unused-argument
        """Execute `cmd` on the target.

        This method runs the specified `cmd` as a command on its target.
        It uses the ssh shell command to run the command and parses the exitcode.
        cmd - command to be run on the target

        returns:
        (stdout, stderr, returncode)
        """
        complete_cmd = "ssh -x {prefix} -p {port} {user}@{host} {cmd}".format(
            user=self.networkservice.username,
            host=self.networkservice.address,
            cmd=cmd,
            prefix=self.ssh_prefix,
            port=self.networkservice.port
        ).split(' ')
        self.logger.debug("Sending command: %s", complete_cmd)
        if self.stderr_merge:
            stderr_pipe = subprocess.STDOUT
        else:
            stderr_pipe = subprocess.PIPE
        try:
            sub = subprocess.Popen(
                complete_cmd, stdout=subprocess.PIPE, stderr=stderr_pipe
            )
        except:
            raise ExecutionError(
                "error executing command: {}".format(complete_cmd)
            )

        stdout, stderr = sub.communicate()
        stdout = stdout.decode(codec, decodeerrors).split('\n')
        stdout.pop()
        if stderr is None:
            stderr = []
        else:
            stderr = stderr.decode(codec, decodeerrors).split('\n')
            stderr.pop()
        return (stdout, stderr, sub.returncode)

    def get_status(self):
        """The SSHDriver is always connected, return 1"""
        return 1

    @Driver.check_active
    @step(args=['filename', 'remotepath'])
    def put(self, filename, remotepath=''):
        transfer_cmd = "scp {prefix} -P {port} {filename} {user}@{host}:{remotepath}".format(
            filename=filename,
            user=self.networkservice.username,
            host=self.networkservice.address,
            remotepath=remotepath,
            prefix=self.ssh_prefix,
            port=self.networkservice.port
        ).split(' ')
        try:
            sub = subprocess.call(
                transfer_cmd
            )  #, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            raise ExecutionError(
                "error executing command: {}".format(transfer_cmd)
            )
        if sub != 0:
            raise ExecutionError(
                "error executing command: {}".format(transfer_cmd)
            )

    @Driver.check_active
    @step(args=['filename', 'destination'])
    def get(self, filename, destination="."):
        transfer_cmd = "scp {prefix} -P {port} {user}@{host}:{filename} {destination}".format(
            filename=filename,
            user=self.networkservice.username,
            host=self.networkservice.address,
            prefix=self.ssh_prefix,
            port=self.networkservice.port,
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
        if sub != 0:
            raise ExecutionError(
                "error executing command: {}".format(transfer_cmd)
            )

    def _cleanup_own_master(self):
        """Exit the controlmaster and delete the tmpdir"""
        complete_cmd = "ssh -x -o ControlPath={cpath} -O exit -p {port} {user}@{host}".format(
            cpath=self.control,
            port=self.networkservice.port,
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
