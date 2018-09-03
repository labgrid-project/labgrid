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
@attr.s(cmp=False)
class SSHDriver(CommandMixin, Driver, CommandProtocol, FileTransferProtocol):
    """SSHDriver - Driver to execute commands via SSH"""
    bindings = {"networkservice": NetworkService, }
    keyfile = attr.ib(default="", validator=attr.validators.instance_of(str))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.logger = logging.getLogger("{}({})".format(self, self.target))

    def on_activate(self):
        self.ssh_opts = "-o LogLevel=ERROR"
        self.ssh_opts += " -i {}".format(os.path.abspath(self.keyfile)
                                          ) if self.keyfile else ""
        self.ssh_opts += " -o PasswordAuthentication=no" if (
            not self.networkservice.password) else ""
        if self.networkservice.options:
            self.ssh_opts += " " + self.networkservice.options

        self.env = os.environ.copy()
        if self.networkservice.password:
            self.sshpass = "sshpass -e "
            self.env['SSHPASS'] = self.networkservice.password
        else:
            self.sshpass = ""

        self.control = self._check_master() if self.networkservice.shared else ""
        self.ssh_opts += " -F /dev/null"
        self.ssh_opts += " -o ControlPath={}".format(
            self.control
        ) if self.control else ""

    def on_deactivate(self):
        if self.networkservice.shared:
            self._cleanup_own_master()

    def _start_own_master(self):
        """Starts a controlmaster connection in a temporary directory."""
        self.tmpdir = tempfile.mkdtemp(prefix='labgrid-ssh-tmp-')
        control = os.path.join(
            self.tmpdir, 'control-{}'.format(self.networkservice.address)
        )
        # use sshpass if we have a password
        args = ("{sshpass}ssh -n -x -o ConnectTimeout={timeout} -o ControlPersist=300 -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no"  # pylint: disable=line-too-long
                " -MN -S {control} -p {port} {opts} {user}@{addr}").format(
                    sshpass=self.sshpass, timeout=self.networkservice.timeout, control=control,
                    port=self.networkservice.port, opts=self.ssh_opts,
                    user=self.networkservice.username, addr=self.networkservice.address).split(" ")

        self.process = subprocess.Popen(args, env=self.env)

        try:
            if self.process.wait(timeout=self.networkservice.timeout) is not 0:
                raise ExecutionError(
                    "failed to connect to {} with {} and {}".
                    format(self.networkservice.address, args, self.process.wait())
                )
        except subprocess.TimeoutExpired:
            raise ExecutionError(
                "failed to connect to {} with {} and {} due to timeout".
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
    def run(self, cmd, codec="utf-8", decodeerrors="strict", timeout=30):
        return self._run(cmd, codec=codec, decodeerrors=decodeerrors, timeout=timeout)

    def _run(self, cmd, codec="utf-8", decodeerrors="strict", timeout=None):
        """Execute `cmd` on the target.

        This method runs the specified `cmd` as a command on its target.
        It uses the ssh shell command to run the command and parses the exitcode.
        cmd - command to be run on the target

        returns:
        (stdout, stderr, returncode)
        """
        complete_cmd = "{sshpass}ssh -x -o ConnectTimeout={timeout} {opts} -p {port} {user}@{host} {cmd}".format(
            sshpass=self.sshpass,
            timeout=timeout if timeout is not None else self.networkservice.timeout,
            opts=self.ssh_opts,
            user=self.networkservice.username,
            host=self.networkservice.address,
            cmd=cmd,
            port=self.networkservice.port
        ).split(' ')
        self.logger.debug("Sending command: %s", complete_cmd)
        try:
            sub = subprocess.Popen(
                complete_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.env
            )
        except:
            raise ExecutionError(
                "error executing command: {}".format(complete_cmd)
            )

        stdout, stderr = sub.communicate()
        stdout = stdout.decode(codec, decodeerrors).split('\n')
        stderr = stderr.decode(codec, decodeerrors).split('\n')
        stdout.pop()
        stderr.pop()
        self.logger.debug('Successfully connected to %s', self.networkservice.address)
        return (stdout, stderr, sub.returncode)

    def get_status(self):
        """The SSHDriver is always connected, return 1"""
        return 1

    @Driver.check_active
    @step(args=['filename', 'remotepath'])
    def put(self, filename, remotepath=''):
        transfer_cmd = "{sshpass}scp {opts} -P {port} {filename} {user}@{host}:{remotepath}".format(
            sshpass=self.sshpass,
            filename=filename,
            user=self.networkservice.username,
            host=self.networkservice.address,
            remotepath=remotepath,
            opts=self.ssh_opts,
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
        if sub is not 0:
            raise ExecutionError(
                "error executing command: {}".format(transfer_cmd)
            )

    @Driver.check_active
    @step(args=['filename', 'destination'])
    def get(self, filename, destination="."):
        transfer_cmd = "{sshpass}scp {opts} -P {port} {user}@{host}:{filename} {dest}".format(
            sshpass=self.sshpass,
            filename=filename,
            user=self.networkservice.username,
            host=self.networkservice.address,
            opts=self.ssh_opts,
            port=self.networkservice.port,
            dest=destination
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
